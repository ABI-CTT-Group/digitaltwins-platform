# util/grant_project_access.rb
person_id = ARGV[0]
project_ids = ARGV[1..-1]

if person_id.nil? || project_ids.empty?
  puts "Usage: rails runner util/grant_project_access.rb <person_id> <project_id_1> [<project_id_2> ...]"
  exit 1
end

person = Person.find_by_id(person_id)
if person.nil?
  puts "ERROR: Could not find Person with ID #{person_id}"
  exit 1
end

puts "Processing for Person: #{person.title} (ID: #{person.id})"

project_ids.each do |proj_id|
  project = Project.find_by_id(proj_id)
  if project.nil?
    puts "ERROR: Could not find Project with ID #{proj_id}"
    next
  end

  puts "--------------------------------------------------"
  puts "Processing Project: #{project.title} (ID: #{project.id})"

  # 1. Ensure the user is a member of the project
  # Find a work_group in this project.
  # If the project has no institutions, it has no work groups.
  work_group = project.work_groups.first
  if work_group.nil?
    puts "  -> ERROR: Project has no institutions/workgroups. Cannot add person to project."
    next
  end

  unless person.work_groups.include?(work_group)
    GroupMembership.create!(person: person, work_group: work_group)
    puts "  -> Added Person to Project via WorkGroup #{work_group.id}."
  else
    puts "  -> Person is already a member of this Project."
  end

  # 2. Update sharing policies for subitems
  items = []
  items += project.investigations.to_a
  items += project.studies.to_a
  items += project.assays.to_a
  
  items += project.sops.to_a if project.respond_to?(:sops)
  items += project.workflows.to_a if project.respond_to?(:workflows)
  items += project.documents.to_a if project.respond_to?(:documents)
  items += project.data_files.to_a if project.respond_to?(:data_files)
  items += project.models.to_a if project.respond_to?(:models)
  items += project.publications.to_a if project.respond_to?(:publications)
  items += project.presentations.to_a if project.respond_to?(:presentations)
  items += project.events.to_a if project.respond_to?(:events)

  # Collect all standard assets if the project responds to it just in case
  items += project.assets.to_a if project.respond_to?(:assets)

  items = items.flatten.compact.uniq

  updated_count = 0
  items.each do |item|
    if item.respond_to?(:policy) && item.policy
      # Add an explicit permission for the Project if it doesn't exist
      # access_type: Policy::ACCESSIBLE (2) gives view & download
      perm = item.policy.permissions.find_by(contributor: project)
      
      updated = false
      if perm
        if perm.access_type < Policy::ACCESSIBLE
          perm.update!(access_type: Policy::ACCESSIBLE)
          updated = true
        end
      else
        item.policy.permissions.create!(contributor: project, access_type: Policy::ACCESSIBLE)
        updated = true
      end

      if updated
        item.policy.save!
        item.touch if item.persisted? # Trigger re-index
        updated_count += 1
      end
    end
  end
  
  puts "  -> Updated sharing permissions to ACCESSIBLE for Project group on #{updated_count} sub-items."
end

puts "=================================================="
puts "Done."
