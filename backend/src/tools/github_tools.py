import os
from langchain_core.tools import tool

@tool
def fetch_github_file(repo_name: str, file_path: str) -> str:
    """Fetches the raw string content of a specific file from a GitHub repository.
    repo_name should be formatted as 'owner/repo' (e.g. 'octocat/Hello-World').
    USE THIS TOOL ONLY for reading files from GitHub repositories.
    DO NOT use Tavily search or web search to read GitHub files.
    """
    token = os.getenv("GITHUB_ACCESS_TOKEN")
    if not token:
        return "Error: GitHub token missing or invalid. Please configure GITHUB_ACCESS_TOKEN."
    
    try:
        from github import Github
        from github.GithubException import GithubException
    except ImportError:
        return "Error: PyGithub is not installed."
        
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        contents = repo.get_contents(file_path)
        # If path is a directory, get_contents returns a list. We expect a file here.
        if isinstance(contents, list):
            return f"Error: '{file_path}' is a directory. Please use list_github_repo_files."
        
        decoded = contents.decoded_content.decode('utf-8')
        if not decoded.strip():
            return "Error: No content found."
        return decoded
    except GithubException as e:
        return f"GitHub Error: {e.data.get('message', str(e))}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def list_github_repo_files(repo_name: str, path: str = "") -> str:
    """Lists directory contents of a GitHub repository to help navigate the tree.
    repo_name should be formatted as 'owner/repo' (e.g. 'octocat/Hello-World').
    Leave path empty to list the root directory.
    USE THIS TOOL ONLY for browsing and navigating GitHub repository structures.
    DO NOT use Tavily search or web search to explore GitHub repos.
    """
    token = os.getenv("GITHUB_ACCESS_TOKEN")
    if not token:
        return "Error: GitHub token missing or invalid. Please configure GITHUB_ACCESS_TOKEN."
        
    try:
        from github import Github
        from github.GithubException import GithubException
    except ImportError:
        return "Error: PyGithub is not installed."
        
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        contents = repo.get_contents(path)
        
        if not isinstance(contents, list):
            return f"Error: '{path}' is a file. Please use fetch_github_file."
            
        result = []
        for content in contents:
            item_type = "DIR" if content.type == "dir" else "FILE"
            result.append(f"[{item_type}] {content.path}")
            
        if not result:
            return "Directory is empty."
        return "\n".join(result)
    except GithubException as e:
        return f"GitHub Error: {e.data.get('message', str(e))}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_github_tools():
    return [fetch_github_file, list_github_repo_files]
