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

def simplify_text(text):
    """Simplify text for better readability"""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Simplify complex sentences
    replacements = {
        r'is a leading and fast growing degree granting institution': 'is a leading institution offering degree programs',
        r'provide quality technical, vocational and technopreneurial education': 'provide quality technical and vocational education',
        r'Beacon in technical and manufacturing technology education': 'Leading institution in technical and manufacturing education',
        r'that is relevant for industry, tailored for entrepreneurship': 'relevant for industry and entrepreneurship',
        r'ensuring you use a valid email address that you have access to': 'using a valid email address you can access',
        r'Create a strong password that includes': 'Create a strong password with',
        r'All requirements of HND': 'All HND requirements',
        r'Journeyman class 1 certificate': 'Journeyman Class 1 certificate'
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text

def format_table_data(text):
    """Format table-like data for better display"""
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Handle course listings (tab-separated)
        if '\t' in line and len(line.split('\t')) >= 2:
            parts = [p.strip() for p in line.split('\t')]
            if 'NC' in line or 'ND' in line or 'HND' in line:
                # Course level line
                course_name = parts[0] if parts[0] else "Various"
                levels = [p for p in parts[1:] if p]
                if levels:
                    formatted_lines.append(f"• <strong>{course_name}</strong>: {', '.join(levels)}")
            elif any(term in line.lower() for term in ['division', 'department', 'course']):
                # Header line - skip or format as bold
                if line.lower() not in ['division', 'department', 'course', 'level']:
                    formatted_lines.append(f"<br><strong>{' | '.join(parts)}</strong>")
        else:
            formatted_lines.append(line)
    
    return '<br>'.join(formatted_lines)

def format_response(text):
    """Format the response text for clean, readable display"""
    if not text:
        return text
    
    # Simplify text first
    text = simplify_text(text)
    
    # Clean up bullet points and lists
    text = re.sub(r'[•]\s*', '<li>', text)
    text = re.sub(r'(\d+)\.\s+', r'<li>', text)  # Numbered lists become bullet points
    text = re.sub(r'o\s+', '<li>', text)  # Subpoints
    
    # Handle lists
    lines = text.split('\n')
    formatted_lines = []
    in_list = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Check if line starts a list item
        if line.startswith('<li>'):
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            content = line[4:].strip()
            # Clean up content
            content = re.sub(r':$', '', content)
            formatted_lines.append(f'<li>{content}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            
            # Handle headings
            if re.match(r'^[A-Z][A-Z\s]+:$', line) or re.match(r'^[A-Z][a-zA-Z\s]+:$', line):
                formatted_lines.append(f'<strong>{line}</strong>')
            elif re.match(r'^\d+\.\d+\s+.+:', line):
                # Numbered sections
                formatted_lines.append(f'<strong>{line}</strong>')
            elif ':' in line and len(line) < 100:
                # Short lines with colons might be labels
                parts = line.split(':', 1)
                if len(parts) == 2 and len(parts[0].strip()) < 30:
                    formatted_lines.append(f'<div class="info-grid"><span class="info-label">{parts[0].strip()}:</span><span class="info-value">{parts[1].strip()}</span></div>')
                else:
                    formatted_lines.append(line)
            else:
                # Regular paragraph
                if line and not line.startswith('<'):
                    # Add periods if missing
                    if not line.endswith(('.', '!', '?', ':', ';')):
                        line += '.'
                    formatted_lines.append(f'<p>{line}</p>')
    
    if in_list:
        formatted_lines.append('</ul>')
    
    # Join and clean up
    result = '\n'.join(formatted_lines)
    
    # Fix double paragraphs
    result = re.sub(r'</p>\s*<p>', '<br>', result)
    
    # Handle steps in instructions
    if any(word in result.lower() for word in ['step', 'visit', 'click', 'enter', 'fill']):
        result = re.sub(r'<p>(\d+)\.\s+(.+?)</p>', r'<div class="step"><strong>Step \1:</strong> \2</div>', result)
    
    # Format course listings
    if 'engineering' in result.lower() or 'commerce' in result.lower():
        result = format_table_data(result)
    
    return result

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
            
            # Add a friendly intro for better responses
            if confidence > 0.7:
                intro = "Here's what I found about that:<br><br>"
                response = intro + response
            elif confidence > 0.5:
                intro = "Based on available information:<br><br>"
                response = intro + response
            
            # Save to chat history
            db.save_chat_history(user_message, response, confidence)
            
            return jsonify({
                'response': response,
                'confidence': round(confidence, 2),
                'matched_question': best_match['question']
            })
        else:
            fallback_response = "I'm sorry, I couldn't find specific information about that. Could you try rephrasing your question or ask about:"
            fallback_response += "<br><br>• Course offerings<br>• Admission requirements<br>• Student portal setup<br>• Available programs"
            fallback_response += "<br><br>Or contact our support team for more specific queries."
            
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