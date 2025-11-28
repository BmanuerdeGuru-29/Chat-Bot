from flask import Flask, render_template, request, jsonify
from database import Database
from models.nlp_model import FAQMatcher
import json
import re

app = Flask(__name__)
db = Database()
faq_matcher = FAQMatcher(db)

# Train the model on startup
faq_matcher.fit()

def format_response(text):
    """Format the response text for better display in chat"""
    if not text:
        return text
    
    # Replace line breaks with proper HTML line breaks
    text = text.replace('\n', '<br>')
    
    # Format bullet points
    text = re.sub(r'•\s*', '• ', text)
    text = re.sub(r'\s*', '• ', text)
    
    # Format numbered lists
    text = re.sub(r'(\d+)\.\s*', r'\1. ', text)
    
    # Format o for subpoints (like in the student portal instructions)
    text = re.sub(r'o\s+', '• ', text)
    
    # Format table-like structures (for course listings)
    lines = text.split('<br>')
    formatted_lines = []
    
    for line in lines:
        # Detect table-like structures (multiple tabs or multiple spaces as separators)
        if '\t' in line and line.count('\t') >= 2:
            # Format as a simple table row
            cells = [cell.strip() for cell in line.split('\t') if cell.strip()]
            if cells:
                formatted_line = '<strong>' + cells[0] + ':</strong> ' + ' | '.join(cells[1:])
                formatted_lines.append(formatted_line)
            continue
        elif '|' in line and line.count('|') >= 2:
            # Format pipe-separated tables
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if len(cells) >= 2:
                formatted_line = '<strong>' + cells[0] + ':</strong> ' + ' | '.join(cells[1:])
                formatted_lines.append(formatted_line)
            continue
        else:
            formatted_lines.append(line)
    
    text = '<br>'.join(formatted_lines)
    
    # Add strong formatting to headings
    text = re.sub(r'(\d+\.\d+\s+.+?):', r'<strong>\1:</strong>', text)
    text = re.sub(r'^(REQUIREMENTS|DURATION|COURSE|NB:)', r'<strong>\1</strong>', text, flags=re.IGNORECASE | re.MULTILINE)
    
    return text

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
        
        # Find best matching FAQ
        best_match, confidence = faq_matcher.find_best_match(user_message)
        
        if best_match and confidence > 0.3:
            response = format_response(best_match['answer'])
            # Save to chat history
            db.save_chat_history(user_message, response, confidence)
            
            return jsonify({
                'response': response,
                'confidence': round(confidence, 2),
                'matched_question': best_match['question']
            })
        else:
            fallback_response = "I'm sorry, I couldn't find a good match for your question. Please try rephrasing or contact support for more specific queries."
            db.save_chat_history(user_message, fallback_response, confidence or 0.0)
            
            return jsonify({
                'response': fallback_response,
                'confidence': round(confidence, 2) if confidence else 0.0,
                'matched_question': None
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/faqs', methods=['GET'])
def get_faqs():
    """Get all FAQs for display"""
    try:
        faqs = db.get_all_faqs()
        return jsonify(faqs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    """Get chat history"""
    try:
        history = db.get_chat_history(limit=50)
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/import', methods=['POST'])
def import_faqs():
    """Admin endpoint to import new FAQs"""
    try:
        faqs = request.json.get('faqs', [])
        imported_count = 0
        
        for faq in faqs:
            db.insert_faq(
                question=faq['question'],
                answer=faq['answer'],
                category=faq.get('category')
            )
            imported_count += 1
        
        # Retrain the model with new FAQs
        faq_matcher.fit()
        
        return jsonify({
            'message': f'Successfully imported {imported_count} FAQs',
            'imported_count': imported_count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)