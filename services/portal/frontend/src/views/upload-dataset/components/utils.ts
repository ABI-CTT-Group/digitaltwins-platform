import axios from 'axios'
import { GitContent } from '@/models/uiTypes';
import yaml from "js-yaml";

export const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now.getTime() - date.getTime())
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
  
  if (diffDays === 1) return '1 day ago'
  if (diffDays < 30) return `${diffDays} days ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
  return `${Math.floor(diffDays / 365)} years ago`
}

export const getRepoNameFromUrl = (url:string) => {
  url = url.replace(/\/+$/, "");
  let name = url.split("/").pop();
  name = name!.replace(/\.git$/, "");
  return name;
}

export const getRepoAuthorFromUrl = (url:string) => {
  url = url.replace(/\.git$/, "").replace(/\/+$/, "");
  const parts = url.split("/");
  return parts[parts.length - 2];
}

export const convertToApiUrl = (repoUrl:string) => {
        repoUrl = repoUrl.replace(/\.git$/, "").replace(/\/$/, "");

        const parts = repoUrl.split("/");
        const owner = parts[parts.length - 2];
        const repo = parts[parts.length - 1];

        return `https://api.github.com/repos/${owner}/${repo}`;
    }

export const getRepoContents = async (url:string, path:string ="") => {
    const rootContentUrl = convertToApiUrl(url) + `/contents/${path}`;
    const res = await axios.get(rootContentUrl);
    return res
}

export const getRepoRootCWLContent = (repository_url:string) => {
  return new Promise<{cwlFile:string, content:any}>((resolve, reject)=>{
    getRepoContents(repository_url).then((res)=>{
      const folders = res!.data as GitContent[];
      let cwlFile = "";
      folders.forEach((item: GitContent)=>{
        if(item.type == 'file' && item.name.endsWith(".cwl")){
              cwlFile = item.name;
              return;
          }
      })
      getRepoContents(repository_url, cwlFile).then((res)=>{
          const contentBase64 = res.data.content;
          const content = atob(contentBase64); // base64 → plain text
          try {
            // try to parse YAML format first
            resolve({
              cwlFile,
              content: yaml.load(content)
            });
          } catch (err) {
            console.warn("YAML parse failed, trying JSON...");
            resolve({
              cwlFile,
              content: JSON.parse(content)
            }); // if it is JSON format
          }
      })
    })
  })
    
}