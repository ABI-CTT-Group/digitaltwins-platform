# util/rollback_api_permissions.rb

puts "=================================================="
puts "Rolling back API permissions for admin"

api_user = User.find_by_login('admin') || User.with_role(:admin).first || User.first
api_person = api_user.person

if api_person.nil?
  puts "ERROR: Could not find the admin person."
  exit 1
end

puts "Found Admin Person: #{api_person.title} (ID: #{api_person.id})"

# Iterate over all Projects
Project.find_each do |project|
  items = []
  items += project.investigations.to_a
  items += project.studies.to_a
  items += project.assays.to_a
  items += project.assets.to_a
  items.uniq!

  updated_count = 0
  items.each do |item|
    if item.respond_to?(:policy) && item.policy
      perm = item.policy.permissions.find_by(contributor: api_person)
      if perm
        perm.destroy
        item.touch if item.persisted?
        updated_count += 1
      end
    end
  end
  puts "  -> Rolled back #{updated_count} sub-items in Project #{project.title}."
end

puts "=================================================="
puts "Done. Admin permissions removed."
