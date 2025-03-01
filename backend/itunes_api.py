import requests
from typing import Dict, List, Optional, Union, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# iTunes Search API base URL
ITUNES_API_BASE_URL = "https://itunes.apple.com/search"
ITUNES_LOOKUP_API_BASE_URL = "https://itunes.apple.com/lookup"

def search_itunes(
    query: str,
    media: str = "podcast",
    entity: Optional[str] = None,
    limit: int = 10,
    country: str = "US",
    additional_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Search for podcasts or podcast episodes using the iTunes Search API.
    
    Args:
        query (str): The search term to query for
        media (str): The media type to search for (default: "podcast")
        entity (Optional[str]): The entity type to search for (e.g., "podcast", "podcastEpisode")
        limit (int): Maximum number of results to return (default: 10)
        country (str): Two-letter country code (default: "US")
        additional_params (Optional[Dict[str, Any]]): Any additional parameters to include in the request
        
    Returns:
        Dict[str, Any]: The API response containing search results or error information
    
    Examples:
        >>> # Search for podcasts with "technology" in the title
        >>> search_itunes("technology podcast", entity="podcast")
        
        >>> # Search for specific podcast episodes about "AI"
        >>> search_itunes("AI", entity="podcastEpisode", limit=5)
    """
    try:
        # Check if we're looking up episodes for a specific podcast
        is_podcast_lookup = (entity == "podcastEpisode" and 
                            additional_params and 
                            "collectionId" in additional_params)
        
        # Use lookup API for podcast episodes by ID
        if is_podcast_lookup:
            podcast_id = additional_params["collectionId"]
            logger.info(f"Looking up episodes for podcast ID: {podcast_id}")
            
            # Prepare lookup parameters
            lookup_params = {
                "id": podcast_id,
                "entity": "podcastEpisode",
                "limit": limit,
                "country": country,
            }
            
            # Make the request to the iTunes Lookup API
            response = requests.get(
                ITUNES_LOOKUP_API_BASE_URL, 
                params=lookup_params, 
                timeout=15
            )
            
        else:
            # Standard search API request
            # Prepare the request parameters
            params = {
                "term": query,
                "media": media,
                "limit": limit,
                "country": country,
            }
            
            # Add entity parameter if provided
            if entity:
                params["entity"] = entity
                
            # Add any additional parameters
            if additional_params:
                params.update(additional_params)
                
            logger.info(f"Searching iTunes with params: {params}")
            
            # Make the request to the iTunes Search API
            response = requests.get(ITUNES_API_BASE_URL, params=params, timeout=15)
        
        # Check for HTTP errors
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Log basic info about results
        result_count = data.get("resultCount", 0)
        logger.info(f"iTunes {'lookup' if is_podcast_lookup else 'search'} returned {result_count} results")
        
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error when searching iTunes: {str(e)}")
        return {"error": f"Request failed: {str(e)}", "resultCount": 0, "results": []}
    except ValueError as e:
        logger.error(f"JSON parsing error: {str(e)}")
        return {"error": f"Failed to parse response: {str(e)}", "resultCount": 0, "results": []}
    except Exception as e:
        logger.error(f"Unexpected error during iTunes search: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}", "resultCount": 0, "results": []}

def format_podcast_results(itunes_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Format iTunes API results into a standardized format for our application.
    
    Args:
        itunes_results (Dict[str, Any]): The raw results from the iTunes Search API
        
    Returns:
        List[Dict[str, Any]]: A list of formatted podcast or episode information
    """
    formatted_results = []
    
    results = itunes_results.get("results", [])
    
    # Skip the first result in lookup responses as it's the podcast itself, not an episode
    if len(results) > 0 and "kind" not in results[0] and "collectionId" in results[0]:
        results = results[1:]  # Skip the podcast entry
    
    for item in results:
        # Handle different kinds of results (podcast vs episode)
        if item.get("kind") == "podcast":
            formatted_item = {
                "id": item.get("collectionId", ""),
                "title": item.get("collectionName", ""),
                "description": item.get("description", item.get("collectionCensoredName", "")),
                "artwork_url": item.get("artworkUrl600", item.get("artworkUrl100", "")),
                "artist": item.get("artistName", ""),
                "feed_url": item.get("feedUrl", ""),
                "genre": item.get("primaryGenreName", ""),
                "release_date": item.get("releaseDate", ""),
                "episode_count": item.get("trackCount", 0),
                "country": item.get("country", ""),
                "type": "podcast"
            }
        elif item.get("kind") == "podcast-episode" or (
            "episodeUrl" in item and "collectionId" in item and "trackId" in item
        ):
            formatted_item = {
                "id": item.get("trackId", ""),
                "podcast_id": item.get("collectionId", ""),
                "podcast_title": item.get("collectionName", ""),
                "title": item.get("trackName", ""),
                "description": item.get("description", ""),
                "artwork_url": item.get("artworkUrl600", item.get("artworkUrl100", "")),
                "audio_url": item.get("episodeUrl", item.get("previewUrl", "")),
                "duration": item.get("trackTimeMillis", 0),
                "release_date": item.get("releaseDate", ""),
                "episode_number": item.get("episodeNumber", ""),
                "season": item.get("seasonNumber", ""),
                "type": "episode"
            }
        else:
            # For any other type of result
            formatted_item = {
                "id": item.get("trackId", item.get("collectionId", "")),
                "title": item.get("trackName", item.get("collectionName", "")),
                "description": item.get("description", ""),
                "artwork_url": item.get("artworkUrl100", ""),
                "type": "unknown"
            }
        
        formatted_results.append(formatted_item)
    
    return formatted_results

# Example usage
if __name__ == "__main__":
    # Example 1: Search for tech podcasts
    tech_podcasts = search_itunes("technology podcast", entity="podcast", limit=5)
    print(f"Found {tech_podcasts.get('resultCount', 0)} tech podcasts")
    
    # Example 2: Search for AI podcast episodes
    ai_episodes = search_itunes("artificial intelligence", entity="podcastEpisode", limit=5)
    print(f"Found {ai_episodes.get('resultCount', 0)} AI podcast episodes")
    
    # Format results
    formatted_podcasts = format_podcast_results(tech_podcasts)
    print(f"First formatted podcast: {formatted_podcasts[0] if formatted_podcasts else 'None'}") 