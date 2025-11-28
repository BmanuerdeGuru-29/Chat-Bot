import nltk
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import string
from sentence_transformers import SentenceTransformer
import json

# Download required NLTK data
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

class FAQMatcher:
    def __init__(self, database):
        self.db = database
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),
            max_features=5000
        )
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.tfidf_matrix = None
        self.faq_data = []
        self.is_fitted = False

    def preprocess_text(self, text):
        """Clean and preprocess text"""
        text = text.lower()
        text = re.sub(f'[{re.escape(string.punctuation)}]', '', text)
        text = ' '.join(text.split())
        return text

    def fit(self):
        """Train the model on existing FAQs"""
        faqs = self.db.get_all_faqs()
        if not faqs:
            return
        
        self.faq_data = faqs
        questions = [self.preprocess_text(faq['question']) for faq in faqs]
        
        # TF-IDF approach
        self.tfidf_matrix = self.vectorizer.fit_transform(questions)
        self.is_fitted = True
        
        # Generate embeddings for semantic search
        self.generate_embeddings()

    def generate_embeddings(self):
        """Generate sentence embeddings for FAQs"""
        questions = [faq['question'] for faq in self.faq_data]
        embeddings = self.sentence_model.encode(questions)
        
        # Store embeddings in database
        for i, faq in enumerate(self.faq_data):
            embedding_json = json.dumps(embeddings[i].tolist())
            query = """
            INSERT INTO faq_embeddings (faq_id, embedding)
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE embedding = %s
            """
            self.db.execute_query(query, (faq['id'], embedding_json, embedding_json))

    def find_best_match(self, user_question, method='hybrid'):
        """Find the best matching FAQ"""
        if not self.is_fitted or not self.faq_data:
            return None, 0.0

        processed_question = self.preprocess_text(user_question)
        
        if method == 'tfidf':
            return self._tfidf_match(processed_question)
        elif method == 'semantic':
            return self._semantic_match(user_question)
        else:  # hybrid
            tfidf_match, tfidf_score = self._tfidf_match(processed_question)
            semantic_match, semantic_score = self._semantic_match(user_question)
            
            # Prefer higher confidence match
            if tfidf_score >= semantic_score:
                return tfidf_match, tfidf_score
            else:
                return semantic_match, semantic_score

    def _tfidf_match(self, processed_question):
        """Match using TF-IDF cosine similarity"""
        question_vector = self.vectorizer.transform([processed_question])
        similarities = cosine_similarity(question_vector, self.tfidf_matrix)
        
        best_match_idx = np.argmax(similarities[0])
        best_score = similarities[0][best_match_idx]
        
        if best_score > 0.3:  # Threshold
            return self.faq_data[best_match_idx], best_score
        return None, best_score

    def _semantic_match(self, user_question):
        """Match using semantic similarity"""
        user_embedding = self.sentence_model.encode([user_question])
        
        # Get embeddings from database
        query = "SELECT fe.faq_id, fe.embedding, f.question, f.answer FROM faq_embeddings fe JOIN faqs f ON fe.faq_id = f.id"
        results = self.db.execute_query(query, fetch=True)
        
        if not results:
            return None, 0.0
        
        best_match = None
        best_score = 0.0
        
        for result in results:
            faq_embedding = np.array(json.loads(result['embedding']))
            similarity = cosine_similarity([user_embedding[0]], [faq_embedding])[0][0]
            
            if similarity > best_score:
                best_score = similarity
                best_match = {
                    'id': result['faq_id'],
                    'question': result['question'],
                    'answer': result['answer']
                }
        
        if best_score > 0.5:  # Higher threshold for semantic matching
            return best_match, best_score
        return None, best_score