# backend/apps/search/services.py

class SearchService:
    @staticmethod
    def configure_index_settings(index):
        """
        Configures Meilisearch index settings including ranking rules, 
        searchable attributes, and typo tolerance parameters.
        """
        index.update_settings({
            "searchableAttributes": [
                "title",
                "description",
                "content",
                "category",
            ],
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {
                    "oneTypo": 4,   # Words with 4+ characters allow 1 typo
                    "twoTypos": 8,  # Words with 8+ characters allow up to 2 typos
                },
                "disableOnWords": [],
                "disableOnAttributes": [],
            },
            # Optional: adjust max typos globally if needed
        })
    
    @staticmethod
    def search_lessons(query_str, limit=10):
        # Implementation of search query execution with Meilisearch client
        # Ensure typo tolerance is respected or passed via search parameters if required
        pass
