document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const resultsList = document.getElementById('results-list');
    const transcriptContainer = document.getElementById('transcript-container');
    const transcriptText = document.getElementById('transcript-text');
    const summarizeButton = document.getElementById('summarize-button');
    const summaryContainer = document.getElementById('summary-container');
    const summaryText = document.getElementById('summary-text');
    const searchTypeSelector = document.getElementById('search-type');
    
    // Search tip elements
    const defaultTip = document.getElementById('search-tip-default');
    const itunesPodcastsTip = document.getElementById('search-tip-itunes-podcasts');
    const itunesEpisodesTip = document.getElementById('search-tip-itunes-episodes');

    // API endpoint base URL (change this if your backend is hosted elsewhere)
    const API_BASE_URL = 'http://127.0.0.1:8000';
    
    // Update search tip based on selected search type
    function updateSearchTip() {
        if (!searchTypeSelector) return;
        
        // Hide all tips
        [defaultTip, itunesPodcastsTip, itunesEpisodesTip].forEach(tip => {
            if (tip) tip.classList.remove('active');
        });
        
        // Show the appropriate tip
        switch (searchTypeSelector.value) {
            case 'itunes_podcasts':
                if (itunesPodcastsTip) itunesPodcastsTip.classList.add('active');
                searchInput.placeholder = "Search for podcasts (e.g., 'technology', 'news')";
                break;
            case 'itunes_episodes':
                if (itunesEpisodesTip) itunesEpisodesTip.classList.add('active');
                searchInput.placeholder = "Search for podcast episodes (e.g., 'interview', 'AI')";
                break;
            default:
                if (defaultTip) defaultTip.classList.add('active');
                searchInput.placeholder = "Search for podcast episodes";
                break;
        }
    }
    
    // Initialize search tip
    updateSearchTip();
    
    // Add event listener for search type changes
    if (searchTypeSelector) {
        searchTypeSelector.addEventListener('change', updateSearchTip);
    }

    // Search for podcast episodes
    async function searchPodcasts(query) {
        try {
            let searchEndpoint;
            let searchType = searchTypeSelector ? searchTypeSelector.value : 'default';
            
            // Determine which endpoint to use based on the search type
            switch (searchType) {
                case 'itunes_podcasts':
                    searchEndpoint = `${API_BASE_URL}/api/itunes/podcasts?query=${encodeURIComponent(query)}`;
                    break;
                case 'itunes_episodes':
                    searchEndpoint = `${API_BASE_URL}/api/itunes/episodes?query=${encodeURIComponent(query)}`;
                    break;
                default:
                    // Fallback to original search endpoint
                    searchEndpoint = `${API_BASE_URL}/api/search?query=${encodeURIComponent(query)}`;
            }
            
            const response = await fetch(searchEndpoint);
            
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            
            const data = await response.json();
            displaySearchResults(data, searchType);
        } catch (error) {
            console.error("Search error:", error);
            alert("Error searching podcasts. Please try again.");
        }
    }

    // Display search results
    function displaySearchResults(episodes, searchType) {
        resultsList.innerHTML = '';
        
        if (episodes.length === 0) {
            resultsList.innerHTML = '<p>No episodes found. Try a different search term.</p>';
            return;
        }

        episodes.forEach(episode => {
            const listItem = document.createElement('li');
            
            // Format the result differently based on the search type and result type
            if (searchType === 'itunes_podcasts' && episode.type === 'podcast') {
                // For iTunes podcast results
                listItem.innerHTML = `
                    <div class="podcast-item">
                        <img src="${episode.artwork_url || 'placeholder.png'}" alt="${episode.title}" class="podcast-artwork">
                        <div class="podcast-info">
                            <h3>${episode.title}</h3>
                            <p class="podcast-author">By ${episode.artist || 'Unknown'}</p>
                            <p>${episode.description || 'No description available'}</p>
                            <p class="podcast-genre">${episode.genre || ''}</p>
                            <button class="search-episodes-button" data-podcast-id="${episode.id}">
                                Find Episodes
                            </button>
                        </div>
                    </div>
                `;
            } else if (searchType === 'itunes_episodes' && episode.type === 'episode') {
                // For iTunes episode results
                // Check if we have a valid audio URL
                const hasAudioUrl = episode.audio_url && episode.audio_url.trim() !== '';
                
                listItem.innerHTML = `
                    <div class="episode-item">
                        <img src="${episode.artwork_url || 'placeholder.png'}" alt="${episode.title}" class="episode-artwork">
                        <div class="episode-info">
                            <h3>${episode.title}</h3>
                            <p class="podcast-title">From: ${episode.podcast_title || 'Unknown Podcast'}</p>
                            <p>${episode.description || 'No description available'}</p>
                            ${hasAudioUrl ? `
                                <button class="transcribe-button" data-url="${episode.audio_url}">
                                    Transcribe Episode
                                </button>
                            ` : '<p class="error-message">No audio URL available for this episode</p>'}
                        </div>
                    </div>
                `;
            } else {
                // For default/original search results
                const audioUrl = episode.audio_url || '';
                
                listItem.innerHTML = `
                    <h3>${episode.title}</h3>
                    <p>${episode.description || ''}</p>
                    <button class="transcribe-button" data-url="${audioUrl}">
                        Transcribe Episode
                    </button>
                `;
            }
            
            resultsList.appendChild(listItem);
        });

        // Add event listeners to transcribe buttons
        document.querySelectorAll('.transcribe-button').forEach(button => {
            button.addEventListener('click', () => {
                const audioUrl = button.getAttribute('data-url');
                transcribeEpisode(audioUrl);
            });
        });
        
        // Add event listeners to search episode buttons
        document.querySelectorAll('.search-episodes-button').forEach(button => {
            button.addEventListener('click', () => {
                const podcastId = button.getAttribute('data-podcast-id');
                if (searchTypeSelector) {
                    searchTypeSelector.value = 'itunes_episodes';
                    updateSearchTip(); // Update the search tip when switching to episodes
                }
                searchItunesEpisodes('', podcastId);
            });
        });
    }
    
    // Search for episodes of a specific podcast
    async function searchItunesEpisodes(query, podcastId) {
        try {
            // Show loading message
            resultsList.innerHTML = '<p>Loading episodes...</p>';
            
            const searchEndpoint = `${API_BASE_URL}/api/itunes/episodes?query=${encodeURIComponent(query || '')}&podcast_id=${podcastId}`;
            
            const response = await fetch(searchEndpoint);
            
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // If we got results, display them
            if (data && data.length > 0) {
                displaySearchResults(data, 'itunes_episodes');
            } else {
                // Try the lookup endpoint as a fallback
                const lookupEndpoint = `${API_BASE_URL}/api/itunes/episodes?podcast_id=${podcastId}`;
                const lookupResponse = await fetch(lookupEndpoint);
                
                if (!lookupResponse.ok) {
                    throw new Error(`HTTP error! Status: ${lookupResponse.status}`);
                }
                
                const lookupData = await lookupResponse.json();
                
                if (lookupData && lookupData.length > 0) {
                    displaySearchResults(lookupData, 'itunes_episodes');
                } else {
                    resultsList.innerHTML = `
                        <p>No episodes found for this podcast. This could be due to:</p>
                        <ul>
                            <li>The podcast doesn't have episodes available through the iTunes API</li>
                            <li>The episodes might be available only through the podcast's website</li>
                            <li>Try searching for episodes directly using the "iTunes Episodes" search type</li>
                        </ul>
                    `;
                }
            }
        } catch (error) {
            console.error("Episode search error:", error);
            resultsList.innerHTML = `<p>Error searching episodes: ${error.message}. Please try again.</p>`;
        }
    }

    // Transcribe a selected episode
    async function transcribeEpisode(audioUrl) {
        try {
            // Show loading indicator with more detailed message
            transcriptText.innerHTML = `
                <div class="loading-message">
                    <p>Transcribing episode... This may take several minutes.</p>
                    <p>For large audio files (>25MB), the system will automatically split the file into smaller chunks 
                    and process each chunk separately, which may take longer.</p>
                    <p>The system will use FFmpeg if available, or fall back to a built-in method if FFmpeg is not installed.</p>
                    <p>Please be patient and do not refresh the page.</p>
                </div>
            `;
            transcriptContainer.style.display = 'block';
            summaryContainer.style.display = 'none';
            
            const response = await fetch(`${API_BASE_URL}/api/transcribe`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ audio_url: audioUrl })
            });
            
            if (!response.ok) {
                // Try to get detailed error message from response
                let errorDetail = "Unknown error";
                try {
                    const errorData = await response.json();
                    errorDetail = errorData.detail || "Unknown error";
                } catch (e) {
                    // If we can't parse the JSON, use the status text
                    errorDetail = response.statusText;
                }
                
                // Format user-friendly error message
                let errorMessage = `Error: ${errorDetail}`;
                
                // Special handling for file size errors
                if (response.status === 400 && 
                    (errorDetail.includes("size limit") || 
                     errorDetail.includes("too large") || 
                     errorDetail.includes("exceeds"))) {
                    errorMessage = `
                        <div class="error-container">
                            <h3>File Size Error</h3>
                            <p>${errorDetail}</p>
                            <p>OpenAI's Whisper API has a 25MB file size limit for audio files.</p>
                            <p>Suggestions:</p>
                            <ul>
                                <li>Try a shorter episode or clip</li>
                                <li>Look for a lower quality version of the audio</li>
                                <li>For podcasts over 25MB, you may need to use a different transcription service</li>
                            </ul>
                        </div>
                    `;
                } else if (response.status === 500 && errorDetail.includes("FFmpeg")) {
                    errorMessage = `
                        <div class="error-container">
                            <h3>FFmpeg Not Available</h3>
                            <p>${errorDetail}</p>
                            <p>The server requires FFmpeg to process large audio files.</p>
                            <p>Please contact the administrator to install FFmpeg on the server.</p>
                        </div>
                    `;
                }
                
                transcriptText.innerHTML = errorMessage;
                throw new Error(errorDetail);
            }
            
            const data = await response.json();
            transcriptText.textContent = data.transcript;
        } catch (error) {
            console.error("Transcription error:", error);
            // Only update the text if it hasn't been updated already with a specific error message
            if (transcriptText.innerHTML.includes("Transcribing episode")) {
                transcriptText.innerHTML = `
                    <div class="error-container">
                        <h3>Transcription Error</h3>
                        <p>Error transcribing episode: ${error.message}</p>
                    </div>
                `;
            }
        }
    }

    // Summarize and extract timestamps from the transcript
    async function summarizeTranscript(transcript) {
        try {
            // Show loading indicator
            summaryText.textContent = "Generating summary...";
            summaryContainer.style.display = 'block';
            
            const response = await fetch(`${API_BASE_URL}/api/summarize`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ transcript })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            
            const data = await response.json();
            summaryText.textContent = data.summary;
        } catch (error) {
            console.error("Summarization error:", error);
            summaryText.textContent = "Error generating summary. Please try again.";
        }
    }

    // Event Listeners
    searchButton.addEventListener('click', () => {
        const query = searchInput.value.trim();
        if (query) {
            searchPodcasts(query);
        }
    });

    // Also search when Enter key is pressed
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const query = searchInput.value.trim();
            if (query) {
                searchPodcasts(query);
            }
        }
    });

    summarizeButton.addEventListener('click', () => {
        const transcript = transcriptText.textContent;
        if (transcript && !transcriptText.innerHTML.includes("Transcribing episode") && !transcriptText.innerHTML.includes("error-container")) {
            summarizeTranscript(transcript);
        } else {
            alert("Please wait for transcription to complete before summarizing, or ensure there are no errors in the transcription.");
        }
    });
}); 