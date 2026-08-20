# update_seek_permissions.rb
Project.find_each do |project|
  puts "=================================================="
  puts "Processing Project: #{project.title}"
  
  # 1. Update Project Default Policy
  if project.default_policy
    if project.default_policy.access_type != Policy::NO_ACCESS
      project.default_policy.access_type = Policy::NO_ACCESS
      project.default_policy.save!
      puts "  -> Updated Project default policy to NO_ACCESS (Private)."
    else
      puts "  -> Project default policy is already NO_ACCESS."
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
      if item.policy.access_type != Policy::NO_ACCESS
        item.policy.access_type = Policy::NO_ACCESS
        item.policy.save!
        
        # Touch the item to ensure it gets re-indexed in Solr for search visibility
        item.touch if item.persisted?
        
        updated_count += 1
      end
    end
  end
  puts "  -> Updated #{updated_count} sub-items to NO_ACCESS."
end
puts "=================================================="
puts "Done."
