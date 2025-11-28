import pandas as pd
import json
from database import Database
import os

class FAQImporter:
    def __init__(self):
        self.db = Database()

    def import_from_csv(self, file_path):
        """Import FAQs from CSV file with proper encoding handling"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    print(f"Successfully read CSV with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # If all encodings fail, try without specifying encoding
                df = pd.read_csv(file_path, encoding_errors='ignore')
                print("Read CSV with encoding errors ignored")
            
            # Check if required columns exist
            required_columns = ['question', 'answer']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                print(f"Missing columns: {missing_columns}")
                print(f"Available columns: {list(df.columns)}")
                return
            
            imported_count = 0
            for _, row in df.iterrows():
                # Skip rows with empty questions or answers
                if pd.notna(row['question']) and pd.notna(row['answer']):
                    self.db.insert_faq(
                        question=str(row['question']).strip(),
                        answer=str(row['answer']).strip(),
                        category=str(row['category']).strip() if 'category' in df.columns and pd.notna(row.get('category')) else None
                    )
                    imported_count += 1
            
            print(f"Imported {imported_count} FAQs from CSV")
            
        except Exception as e:
            print(f"Error importing from CSV: {e}")

    def import_from_excel(self, file_path):
        """Import FAQs from Excel file"""
        try:
            df = pd.read_excel(file_path)
            
            # Check if required columns exist
            required_columns = ['question', 'answer']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                print(f"Missing columns: {missing_columns}")
                print(f"Available columns: {list(df.columns)}")
                return
            
            imported_count = 0
            for _, row in df.iterrows():
                # Skip rows with empty questions or answers
                if pd.notna(row['question']) and pd.notna(row['answer']):
                    self.db.insert_faq(
                        question=str(row['question']).strip(),
                        answer=str(row['answer']).strip(),
                        category=str(row['category']).strip() if 'category' in df.columns and pd.notna(row.get('category')) else None
                    )
                    imported_count += 1
            
            print(f"Imported {imported_count} FAQs from Excel")
            
        except Exception as e:
            print(f"Error importing from Excel: {e}")

    def import_from_json(self, file_path):
        """Import FAQs from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                faqs = json.load(f)
            
            # Handle both list format and object format
            if isinstance(faqs, dict):
                # Convert dict to list if needed
                faqs = list(faqs.values())
            
            imported_count = 0
            for faq in faqs:
                if isinstance(faq, dict) and 'question' in faq and 'answer' in faq:
                    self.db.insert_faq(
                        question=str(faq['question']).strip(),
                        answer=str(faq['answer']).strip(),
                        category=str(faq['category']).strip() if 'category' in faq and faq['category'] else None
                    )
                    imported_count += 1
            
            print(f"Imported {imported_count} FAQs from JSON")
            
        except Exception as e:
            print(f"Error importing from JSON: {e}")

    def import_from_text(self, file_path, delimiter="|"):
        """Import FAQs from text file with custom delimiter"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            imported_count = 0
            for line in lines:
                if delimiter in line:
                    parts = line.strip().split(delimiter)
                    if len(parts) >= 2:
                        question = parts[0].strip()
                        answer = parts[1].strip()
                        category = parts[2].strip() if len(parts) > 2 else None
                        
                        if question and answer:  # Only import if both fields are non-empty
                            self.db.insert_faq(question, answer, category)
                            imported_count += 1
            
            print(f"Imported {imported_count} FAQs from text file")
            
        except Exception as e:
            print(f"Error importing from text file: {e}")

    def auto_import(self, file_path):
        """Automatically detect file type and import"""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.csv':
            self.import_from_csv(file_path)
        elif file_extension in ['.xlsx', '.xls']:
            self.import_from_excel(file_path)
        elif file_extension == '.json':
            self.import_from_json(file_path)
        elif file_extension == '.txt':
            self.import_from_text(file_path)
        else:
            print(f"Unsupported file format: {file_extension}")
            print("Supported formats: .csv, .xlsx, .xls, .json, .txt")

# Example usage
if __name__ == "__main__":
    importer = FAQImporter()
    
    # Use auto_import to automatically detect file type
    file_path = 'faq.xls'  # Change this to your actual file path
    
    if os.path.exists(file_path):
        importer.auto_import(file_path)
    else:
        print(f"File not found: {file_path}")
        print("Please make sure the file exists in the same directory")