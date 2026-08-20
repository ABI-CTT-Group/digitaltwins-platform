# util/grant_api_permissions.rb

puts "=================================================="
puts "Granting explicit API permissions to private items"

# Find the API user from command line argument
api_user_identifier = ARGV[0]
if api_user_identifier.nil? || api_user_identifier.empty?
  puts "ERROR: Please provide the email or login of the API user."
  puts "Usage: rails runner util/grant_api_permissions.rb <email_or_login>"
  exit 1
end

api_user = User.find_by_login(api_user_identifier) || User.joins(:person).where(people: { email: api_user_identifier }).first
api_person = api_user&.person

if api_person.nil?
  puts "ERROR: Could not find a person with login or email: #{api_user_identifier}"
  exit 1
end

puts "Found API Person: #{api_person.title} (ID: #{api_person.id})"

# Iterate over all Projects
Project.find_each do |project|
  puts "--------------------------------------------------"
  puts "Processing Project: #{project.title}"

  # 1. Projects in SEEK don't have a direct policy. They are inherently public/visible
  # to anyone unless explicitly hidden by other configuration.

  # 2. Ensure Default Policy for new items is NO_ACCESS
  if project.default_policy
    project.default_policy.access_type = Policy::NO_ACCESS
    project.default_policy.save!
    puts "  -> Project default policy for new items is NO_ACCESS."
  end

  # 3. Collect all subitems
  items = []
  items += project.investigations.to_a
  items += project.studies.to_a
  items += project.assays.to_a
  items += project.assets.to_a
  items.uniq!

  updated_count = 0
  items.each do |item|
    if item.respond_to?(:policy) && item.policy
      # Make sure the item itself is NO_ACCESS (Private)
      item.policy.access_type = Policy::NO_ACCESS
      
      # Add an explicit permission for the API Person if it doesn't exist
      unless item.policy.permissions.exists?(contributor: api_person)
        item.policy.permissions.build(contributor: api_person, access_type: Policy::VISIBLE)
      end
      
      # If the permission exists but access type is lower, we could update it, 
      # but build/create handles new ones. Let's just update existing if needed:
      perm = item.policy.permissions.find_by(contributor: api_person)
      if perm && perm.access_type < Policy::VISIBLE
        perm.update(access_type: Policy::VISIBLE)
      end

      item.policy.save!
      
      # Touch the item to trigger Solr re-index so API can immediately search it
      item.touch if item.persisted?
      
      updated_count += 1
    end
  end
  puts "  -> Processed #{updated_count} sub-items (Set to NO_ACCESS + API Permission)."
end

puts "=================================================="
puts "Done. All subitems are now private, but accessible by the API service account."
