# seek-prune.rb — runs INSIDE a throwaway SEEK (ldh) sandbox via `rails runner`,
# against a copy of the source SEEK DB + filestore. Never point it at a live SEEK.
#
# Keeps only KEEP_PROGRAMME / KEEP_PROJECT and their content; removes every other
# programme/project tree, every asset outside the kept project, people not needed
# by kept content, unused institutions; scrubs secrets (tokens, sessions, password
# hashes, encrypted settings). Writes reports to /out:
#   forbidden.txt  — strings (titles/names/emails) of everything removed, for the leak scan
#   keep-files.txt — filestore paths (relative) still referenced after the prune
require 'set'

keep_prog = ENV.fetch('KEEP_PROGRAMME').to_i
keep_proj = ENV.fetch('KEEP_PROJECT').to_i
admin_sub = ENV.fetch('ADMIN_SUB')
stale_sops = ENV.fetch('STALE_SOP_IDS', '').split(',').map(&:to_i)
out = '/out'

# no Solr in the sandbox: swallow index/remove calls in memory
Sunspot.session = Sunspot::Rails::StubSessionProxy.new(Sunspot.session)

REMAINING = %w[Programme Project Investigation Study Assay DataFile Model Sop Workflow
               Document Presentation Publication Event Collection Sample SampleType Strain].freeze
ident = Identity.find_by(provider: 'oidc', uid: admin_sub)
admin_person = ident && User.find_by(id: ident.user_id)&.person
abort("seek-prune: admin identity not found (identity=#{ident.inspect})") unless admin_person
puts "admin: person #{admin_person.id} #{admin_person.name}"
forbidden = Set.new
note = ->(*strs) { strs.compact.map(&:to_s).map(&:strip).each { |s| forbidden << s if s.length >= 6 } }
destroy = lambda do |obj|
  note.call(obj.try(:title), obj.try(:description))
  obj.reload.destroy!
rescue ActiveRecord::RecordNotFound
  nil
end

Seek::Permissions::Authorization.disable_authorization_checks do
  ActiveRecord::Base.transaction do
    # 1. other ISA trees (same bottom-up order as util/rm-seek-tree.sh)
    Project.where.not(id: keep_proj).to_a.each do |proj|
      proj.investigations.to_a.each do |inv|
        inv.studies.to_a.each { |s| s.assays.to_a.each { |a| destroy.call(a) }; destroy.call(s) }
        destroy.call(inv)
      end
    end

    # 2. assets / leftover ISA outside the kept project (+ stale SOP links)
    # Template/FileTemplate rows are SEEK seed data — left alone.
    %w[Assay Study Investigation DataFile Model Sop Workflow Document Presentation
       Publication Event Collection Sample SampleType Strain Placeholder].each do |k|
      next unless Object.const_defined?(k)
      k.constantize.all.to_a.each do |i|
        next unless i.respond_to?(:projects)
        destroy.call(i) unless i.projects.map(&:id).include?(keep_proj)
      end
    end
    stale_sops.each do |sid|
      s = Sop.find_by(id: sid)
      destroy.call(s) if s && (s.workflows.to_a rescue []).empty?
    end

    # 3. projects / programmes
    Project.where.not(id: keep_proj).to_a.each { |p| destroy.call(p) }
    Programme.where.not(id: keep_prog).to_a.each { |p| destroy.call(p) }

    # 4. people: keep admin + contributors/creators of everything that remains
    keep_people = Set[admin_person.id]
    REMAINING.each do |k|
      next unless Object.const_defined?(k)
      k.constantize.all.to_a.each do |i|
        keep_people << i.contributor_id if i.respond_to?(:contributor_id) && i.contributor_id
        keep_people.merge(i.creators.map(&:id)) if i.respond_to?(:creators)
      end
    end
    Person.where.not(id: keep_people.to_a).to_a.each do |p|
      note.call(p.name, p.email, p.try(:first_name), p.try(:last_name))
      u = p.user
      p.reload.destroy!
      u&.reload&.destroy! rescue nil
    end
    User.where(person_id: nil).or(User.where.not(person_id: Person.select(:id))).to_a.each do |u|
      note.call(u.login, u.try(:email))
      u.destroy!
    end

    # 5. institutions no longer used by a kept project or person
    Institution.all.to_a.each do |inst|
      used = inst.projects.any? || inst.people.any?
      destroy.call(inst) unless used
    end
  end
end

conn = ActiveRecord::Base.connection

# 5b. dangling polymorphic rows (content blobs, git repos/versions, annotations,
# creators, relationships, …) whose target was destroyed above. Generic rule:
# any <x>_type/<x>_id column pair whose referenced record no longer exists.
dangling = 0
conn.tables.each do |t|
  cols = conn.columns(t).map(&:name)
  cols.grep(/_type\z/).each do |tc|
    ic = tc.sub(/_type\z/, '_id')
    next unless cols.include?(ic)
    conn.select_rows("SELECT DISTINCT #{tc} FROM #{t} WHERE #{tc} IS NOT NULL").flatten.each do |type|
      klass = type.safe_constantize
      next unless klass.is_a?(Class) && klass < ActiveRecord::Base && klass.table_exists?
      ids_sql = "SELECT #{klass.primary_key} FROM #{klass.table_name}"
      if t == 'content_blobs'
        conn.select_rows("SELECT original_filename FROM content_blobs WHERE asset_type = #{conn.quote(type)} " \
                         "AND asset_id NOT IN (#{ids_sql})").flatten.each { |f| note.call(f) }
      end
      n = conn.delete("DELETE FROM #{t} WHERE #{tc} = #{conn.quote(type)} AND #{ic} IS NOT NULL " \
                      "AND #{ic} NOT IN (#{ids_sql})")
      if n.positive?
        dangling += n
        puts "dangling: #{t}.#{tc}=#{type} -> #{n} row(s) deleted"
      end
    end
  end
end
puts "dangling polymorphic rows deleted: #{dangling}"

# 6. scrub secrets / logs (raw SQL — these must not travel at all)
%w[api_tokens sessions oauth_access_grants oauth_access_tokens oauth_applications
   oauth_sessions delayed_jobs activity_logs message_logs].each do |t|
  conn.execute("DELETE FROM #{t}") if conn.table_exists?(t)
end
conn.execute("UPDATE settings SET encrypted_value = NULL, encrypted_value_iv = NULL WHERE encrypted_value IS NOT NULL")
conn.execute("UPDATE openbis_endpoints SET encrypted_password = NULL, encrypted_password_iv = NULL") if conn.table_exists?('openbis_endpoints')
# kept users: unusable random hashes; target sets a new password via util/set-seek-password.sh
User.all.each do |u|
  u.update_columns(crypted_password: SecureRandom.hex(32), salt: SecureRandom.hex(20),
                   remember_token: nil, remember_token_expires_at: nil,
                   reset_password_code: nil, reset_password_code_until: nil)
end

# 7. filestore paths still referenced
fs = File.expand_path(Seek::Config.filestore_path, Rails.root.to_s)
keep_files = []
ContentBlob.all.each do |b|
  p = b.filepath
  keep_files << p if p && File.exist?(p)
  keep_files.concat(Dir.glob(File.join(fs, 'converted-assets', "#{b.uuid}*")))
end
Git::Repository.all.each { |r| keep_files << r.local_path if File.exist?(r.local_path) }
Avatar.all.each { |a| keep_files.concat(Dir.glob(File.join(fs, 'avatars', '**', "#{a.id}.*"))) }
ModelImage.all.each { |m| keep_files.concat(Dir.glob(File.join(fs, 'model_images', '**', "#{m.id}.*"))) } if defined?(ModelImage)
File.write("#{out}/keep-files.txt", keep_files.map { |p| File.expand_path(p, Rails.root.to_s) }.uniq.map { |p| p.delete_prefix("#{fs}/") }.sort.join("\n") + "\n")

# don't flag strings that legitimately survive (substrings of kept titles/names)
kept_text = []
REMAINING.each do |k|
  next unless Object.const_defined?(k)
  k.constantize.all.each { |i| kept_text << i.try(:title).to_s << i.try(:description).to_s }
end
Person.all.each { |p| kept_text << p.name.to_s << p.email.to_s }
Institution.all.each { |i| kept_text << i.title.to_s }
kept_blob = kept_text.join("\n")
File.write("#{out}/forbidden.txt", forbidden.reject { |s| kept_blob.include?(s) }.sort.join("\n") + "\n")

puts "== kept =="
puts "programmes: #{Programme.pluck(:id, :title).inspect}"
puts "projects: #{Project.pluck(:id, :title).inspect}"
puts "investigations=#{Investigation.count} studies=#{Study.count} assays=#{Assay.pluck(:id).inspect}"
puts "workflows=#{Workflow.pluck(:id).sort.inspect} sops=#{Sop.pluck(:id).sort.inspect} data_files=#{DataFile.count}"
puts "people=#{Person.pluck(:id, :first_name, :last_name).inspect}"
puts "users=#{User.count} institutions=#{Institution.pluck(:title).inspect}"
puts "keep-files=#{keep_files.uniq.size} forbidden-strings=#{File.read("#{out}/forbidden.txt").lines.size}"
