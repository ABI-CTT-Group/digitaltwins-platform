# revert_seek_permissions.rb
Project.find_each do |project|
  puts "=================================================="
  puts "Processing Project: #{project.title}"
  
  # 1. Update Project Default Policy
  if project.default_policy
    if project.default_policy.access_type == Policy::NO_ACCESS
      # Revert to ACCESSIBLE (or VISIBLE, depending on your needs)
      project.default_policy.access_type = Policy::ACCESSIBLE
      project.default_policy.save!
      puts "  -> Reverted Project default policy to ACCESSIBLE."
    else
      puts "  -> Project default policy is not NO_ACCESS."
    end
  else
    puts "  -> Project has no default policy."
  end

  # 2. Update all associated structural items and assets
  items = []
  items += project.investigations.to_a
  items += project.studies.to_a
  items += project.assays.to_a
  items += project.assets.to_a
  
  items.uniq!

  updated_count = 0
  items.each do |item|
    if item.respond_to?(:policy) && item.policy
      if item.policy.access_type == Policy::NO_ACCESS
        item.policy.access_type = Policy::ACCESSIBLE
        item.policy.save!
        
        # Touch the item to ensure it gets re-indexed in Solr for search visibility
        item.touch if item.persisted?
        
        updated_count += 1
      end
    end
  end
  puts "  -> Reverted #{updated_count} sub-items to ACCESSIBLE."
end
puts "=================================================="
puts "Done."
