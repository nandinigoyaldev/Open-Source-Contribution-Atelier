"""
Advanced search engine with relevance scoring and semantic understanding.
"""

import logging
import re
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from django.db.models import Q, F, Value
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from apps.advanced_search.models import SearchEmbedding, UserSearchProfile

logger = logging.getLogger(__name__)


class AdvancedSearchEngine:
    """
    Advanced search engine with relevance scoring and semantic understanding.
    """
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.semantic_enabled = getattr(settings, 'SEMANTIC_SEARCH_ENABLED', True)
        self.relevance_weight = 0.6
        self.semantic_weight = 0.4
    
    def search(
        self,
        query: str,
        user,
        filters: Dict = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """
        Perform advanced search with relevance scoring.
        
        Args:
            query: Search query
            user: User for personalization
            filters: Optional filters
            limit: Results limit
            offset: Results offset
        
        Returns:
            Tuple of (results, total_count)
        """
        start_time = time.time()
        
        # Process query
        processed_query = self._process_query(query)
        
        # Get user profile
        profile = self._get_user_profile(user)
        
        # Perform search
        results, total = self._search_content(processed_query, filters, limit + offset)
        
        # Apply relevance scoring
        results = self._apply_relevance_scoring(results, query, user, profile)
        
        # Apply semantic search
        if self.semantic_enabled:
            semantic_results = self._semantic_search(query, filters, limit + offset)
            results = self._merge_results(results, semantic_results)
        
        # Personalize results
        results = self._personalize_results(results, user, profile)
        
        # Add filter suggestions
        filter_suggestions = self._get_filter_suggestions(query, results)
        
        # Log search
        self._log_search(query, user, results, start_time)
        
        # Paginate
        paginated = results[offset:offset + limit]
        
        return paginated, len(results), filter_suggestions
    
    def _process_query(self, query: str) -> Dict[str, Any]:
        """
        Process and understand the query.
        
        Returns:
            Dict with processed query and intent
        """
        query = query.strip().lower()
        
        # Detect intent
        intent = 'general'
        if any(word in query for word in ['how to', 'learn', 'tutorial']):
            intent = 'learning'
        elif any(word in query for word in ['fix', 'bug', 'issue', 'error']):
            intent = 'debugging'
        elif any(word in query for word in ['implement', 'create', 'build']):
            intent = 'development'
        elif any(word in query for word in ['best', 'recommend', 'suggest']):
            intent = 'recommendation'
        
        # Extract keywords
        keywords = [w for w in query.split() if len(w) > 2 and w not in stopwords]
        
        return {
            'original': query,
            'keywords': keywords,
            'intent': intent,
            'cleaned': ' '.join(keywords)
        }
    
    def _search_content(self, processed_query: Dict, filters: Dict, limit: int) -> Tuple[List[Dict], int]:
        """
        Perform base search on content.
        """
        # This is a placeholder - actual implementation depends on content models
        # For now, return empty results
        # In production, this would search through SearchDocument or similar
        return [], 0
    
    def _apply_relevance_scoring(
        self,
        results: List[Dict],
        query: str,
        user,
        profile: Optional[UserSearchProfile]
    ) -> List[Dict]:
        """
        Apply relevance scoring to results.
        """
        for result in results:
            score = 0.0
            
            # Keyword matching score
            keyword_score = self._calculate_keyword_score(result, query)
            score += keyword_score * self.relevance_weight
            
            # User interest score
            if profile and profile.inferred_interests:
                interest_score = self._calculate_interest_score(result, profile)
                score += interest_score * (1 - self.relevance_weight)
            
            # Freshness boost
            if 'created_at' in result:
                days_old = (timezone.now() - result['created_at']).days
                freshness_boost = max(0, 1 - days_old / 365)
                score += freshness_boost * 0.1
            
            # Popularity boost
            if 'popularity' in result:
                popularity_score = result['popularity'] * 0.05
                score += popularity_score
            
            result['relevance_score'] = min(score, 1.0)
        
        # Sort by relevance score
        results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return results
    
    def _calculate_keyword_score(self, result: Dict, query: str) -> float:
        """
        Calculate keyword matching score.
        """
        text = f"{result.get('title', '')} {result.get('description', '')} {result.get('content', '')}".lower()
        query_words = query.lower().split()
        
        matches = sum(1 for word in query_words if word in text)
        return matches / len(query_words) if query_words else 0
    
    def _calculate_interest_score(self, result: Dict, profile: UserSearchProfile) -> float:
        """
        Calculate interest match score.
        """
        if not profile.inferred_interests:
            return 0.5
        
        # Check if result matches any interest
        text = f"{result.get('title', '')} {result.get('description', '')}".lower()
        interests = [i.lower() for i in profile.inferred_interests]
        
        matches = sum(1 for interest in interests if interest in text)
        return min(matches / len(interests), 1.0)
    
    def _semantic_search(self, query: str, filters: Dict, limit: int) -> List[Dict]:
        """
        Perform semantic search using embeddings.
        """
        # Generate query embedding
        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return []
        
        # Get embeddings from database
        embeddings = SearchEmbedding.objects.all()
        results = []
        
        for emb in embeddings:
            if emb.embedding:
                similarity = cosine_similarity(
                    [query_embedding],
                    [emb.embedding]
                )[0][0]
                
                if similarity > 0.3:  # Threshold
                    results.append({
                        'content_type': emb.content_type,
                        'object_id': emb.object_id,
                        'semantic_score': similarity,
                        'is_semantic': True
                    })
        
        results.sort(key=lambda x: x['semantic_score'], reverse=True)
        return results[:limit]
    
    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Get embedding for text.
        """
        # Try to get from cache
        cache_key = f"embedding_{hash(text)}"
        cached = cache.get(cache_key)
        if cached is not None:
            return np.array(cached)
        
        try:
            # Try OpenAI embeddings
            import openai
            response = openai.Embedding.create(
                model="text-embedding-ada-002",
                input=text[:8000]
            )
            embedding = np.array(response['data'][0]['embedding'])
            
            # Cache for 24 hours
            cache.set(cache_key, embedding.tolist(), 86400)
            return embedding
            
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            return None
    
    def _merge_results(self, base_results: List[Dict], semantic_results: List[Dict]) -> List[Dict]:
        """
        Merge base and semantic results.
        """
        # Create lookup for existing results
        existing = {f"{r.get('content_type')}_{r.get('object_id')}": r for r in base_results}
        
        # Add semantic results
        for semantic in semantic_results:
            key = f"{semantic['content_type']}_{semantic['object_id']}"
            if key in existing:
                # Update existing result
                existing[key]['semantic_score'] = semantic['semantic_score']
                existing[key]['relevance_score'] = (
                    existing[key].get('relevance_score', 0) * 0.7 +
                    semantic['semantic_score'] * 0.3
                )
            else:
                # Add new result
                base_results.append(semantic)
        
        return base_results
    
    def _personalize_results(self, results: List[Dict], user, profile: Optional[UserSearchProfile]) -> List[Dict]:
        """
        Personalize results based on user behavior.
        """
        if not profile:
            return results
        
        # Boost previously clicked results
        for result in results:
            result_id = result.get('id')
            if result_id and result_id in profile.clicked_results:
                result['relevance_score'] = min(result.get('relevance_score', 0) + 0.2, 1.0)
        
        # Sort by updated score
        results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return results
    
    def _get_filter_suggestions(self, query: str, results: List[Dict]) -> Dict[str, Any]:
        """
        Generate smart filter suggestions based on query and results.
        """
        suggestions = {
            'categories': [],
            'difficulties': [],
            'tags': [],
            'content_types': [],
        }
        
        if not results:
            return suggestions
        
        # Extract categories
        categories = {}
        for r in results[:20]:
            cat = r.get('category')
            if cat:
                categories[cat] = categories.get(cat, 0) + 1
        
        # Sort by frequency
        suggestions['categories'] = sorted(
            categories.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Extract difficulties
        difficulties = {}
        for r in results[:20]:
            diff = r.get('difficulty')
            if diff:
                difficulties[diff] = difficulties.get(diff, 0) + 1
        
        suggestions['difficulties'] = sorted(
            difficulties.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Extract tags
        tags = {}
        for r in results[:20]:
            for tag in r.get('tags', []):
                if tag:
                    tags[tag] = tags.get(tag, 0) + 1
        
        suggestions['tags'] = sorted(
            tags.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Extract content types
        content_types = {}
        for r in results[:20]:
            ct = r.get('content_type')
            if ct:
                content_types[ct] = content_types.get(ct, 0) + 1
        
        suggestions['content_types'] = sorted(
            content_types.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return suggestions
    
    def _get_user_profile(self, user) -> Optional[UserSearchProfile]:
        """
        Get user search profile.
        """
        if not user or not user.is_authenticated:
            return None
        
        try:
            return UserSearchProfile.objects.get(user=user)
        except UserSearchProfile.DoesNotExist:
            return None
    
    def _log_search(self, query: str, user, results: List[Dict], start_time: float):
        """
        Log search for analytics and personalization.
        """
        response_time = (time.time() - start_time) * 1000
        
        # Update user profile
        if user and user.is_authenticated:
            try:
                profile = UserSearchProfile.objects.get(user=user)
                profile.add_search_query(
                    query,
                    results[:10],
                    [r.get('id') for r in results[:5]]
                )
            except UserSearchProfile.DoesNotExist:
                pass


# ============================================================
# Helper: Stopwords
# ============================================================

stopwords = {
    'a', 'an', 'the', 'and', 'or', 'but', 'for', 'nor', 'on', 'at', 'to', 'by',
    'in', 'with', 'without', 'of', 'as', 'so', 'yet', 'if', 'then', 'else', 'when',
    'where', 'which', 'who', 'whom', 'whose', 'what', 'why', 'how', 'etc', 'e.g',
    'i.e', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am', 'do', 'does',
    'did', 'done', 'doing', 'will', 'shall', 'may', 'might', 'must', 'can', 'could',
    'would', 'should', 'have', 'has', 'had', 'having', 'use', 'using', 'used'
}