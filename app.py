
"""
Cloud-Powered Notes Sharing System with SQLite and Real File Storage
Install required packages first:
!pip install gradio pandas pillow
"""

import gradio as gr
import pandas as pd
import sqlite3
import hashlib
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json

# ============================================================================
# DATABASE SETUP AND MANAGEMENT
# ============================================================================

class NotesDatabase:
    """SQLite database manager for notes and users"""

    def __init__(self, db_path="notes_system.db", storage_dir="uploaded_files"):
        self.db_path = db_path
        self.storage_dir = storage_dir
        self.current_user = None

        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_dir, exist_ok=True)

        # Initialize database
        self._init_database()
        self._create_demo_data()

    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT DEFAULT 'student',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT,
                uploader_id INTEGER NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                downloads INTEGER DEFAULT 0,
                tags TEXT,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER,
                rating_sum INTEGER DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                FOREIGN KEY (uploader_id) REFERENCES users(id)
            )
        """)

        # Downloads table (track who downloaded what)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES notes(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Ratings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                review TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(note_id, user_id),
                FOREIGN KEY (note_id) REFERENCES notes(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.commit()
        conn.close()

    def _create_demo_data(self):
        """Create demo users and sample notes"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if demo data already exists
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return

        # Create demo users
        demo_users = [
            ("admin", "admin123", "admin@university.edu", "admin"),
            ("student1", "pass123", "student1@university.edu", "student"),
            ("professor", "prof123", "professor@university.edu", "teacher")
        ]

        for username, password, email, role in demo_users:
            cursor.execute("""
                INSERT INTO users (username, password, email, role)
                VALUES (?, ?, ?, ?)
            """, (username, self._hash_password(password), email, role))

        # Create sample notes with dummy files
        sample_notes = [
            {
                "title": "Introduction to Python Programming",
                "category": "Computer Science",
                "subject": "Programming",
                "description": "Comprehensive guide covering Python basics, data structures, OOP, and best practices for beginners",
                "uploader_id": 1,
                "tags": json.dumps(["python", "programming", "basics", "oop"]),
                "file_name": "intro_python.pdf"
            },
            {
                "title": "Calculus I - Derivatives and Integrals",
                "category": "Mathematics",
                "subject": "Calculus",
                "description": "Complete notes on differential and integral calculus with solved examples and practice problems",
                "uploader_id": 2,
                "tags": json.dumps(["calculus", "derivatives", "integrals", "mathematics"]),
                "file_name": "calculus_notes.pdf"
            },
            {
                "title": "Database Management Systems",
                "category": "Computer Science",
                "subject": "Databases",
                "description": "SQL, normalization, transactions, indexing, and database design patterns",
                "uploader_id": 1,
                "tags": json.dumps(["database", "sql", "dbms", "normalization"]),
                "file_name": "dbms_notes.pdf"
            },
            {
                "title": "Organic Chemistry Reactions",
                "category": "Chemistry",
                "subject": "Organic Chemistry",
                "description": "Common organic reactions, mechanisms, and synthesis strategies",
                "uploader_id": 3,
                "tags": json.dumps(["chemistry", "organic", "reactions", "mechanisms"]),
                "file_name": "organic_chem.pdf"
            },
            {
                "title": "Data Structures and Algorithms",
                "category": "Computer Science",
                "subject": "DSA",
                "description": "Arrays, linked lists, trees, graphs, sorting, searching, and dynamic programming",
                "uploader_id": 2,
                "tags": json.dumps(["dsa", "algorithms", "data-structures", "programming"]),
                "file_name": "dsa_notes.pdf"
            }
        ]

        for note in sample_notes:
            # Create dummy file
            file_path = os.path.join(self.storage_dir, note["file_name"])
            with open(file_path, "w") as f:
                f.write(f"Sample content for {note['title']}\n")
                f.write("This is a demo file created for the notes sharing system.\n")

            file_size = os.path.getsize(file_path)

            cursor.execute("""
                INSERT INTO notes (title, category, subject, description, uploader_id,
                                 tags, file_path, file_name, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (note["title"], note["category"], note["subject"], note["description"],
                  note["uploader_id"], note["tags"], file_path, note["file_name"], file_size))

        conn.commit()
        conn.close()

    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate(self, username: str, password: str) -> Tuple[bool, str, Optional[int]]:
        """Authenticate user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, password, role FROM users WHERE username = ?
        """, (username,))

        user = cursor.fetchone()
        conn.close()

        if user and user['password'] == self._hash_password(password):
            self.current_user = {
                'id': user['id'],
                'username': user['username'],
                'role': user['role']
            }
            return True, f"Welcome back, {username}!", user['id']

        return False, "Invalid username or password", None

    def register_user(self, username: str, password: str, email: str) -> Tuple[bool, str]:
        """Register new user"""
        if len(username) < 3:
            return False, "Username must be at least 3 characters"
        if len(password) < 6:
            return False, "Password must be at least 6 characters"

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (username, password, email, role)
                VALUES (?, ?, ?, 'student')
            """, (username, self._hash_password(password), email))
            conn.commit()
            conn.close()
            return True, "Registration successful! Please login."
        except sqlite3.IntegrityError:
            conn.close()
            return False, "Username already exists"

    def add_note(self, title: str, category: str, subject: str,
                 description: str, tags: str, file) -> Tuple[bool, str]:
        """Add new note with file"""
        if not self.current_user:
            return False, "Please login first"

        if not file:
            return False, "Please upload a file"

        if not title or not category or not subject:
            return False, "Please fill all required fields"

        # Save file
        file_name = os.path.basename(file.name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_file_name = f"{timestamp}_{file_name}"
        file_path = os.path.join(self.storage_dir, unique_file_name)

        try:
            shutil.copy(file.name, file_path)
            file_size = os.path.getsize(file_path)

            # Insert into database
            conn = self._get_connection()
            cursor = conn.cursor()

            tags_list = json.dumps([tag.strip() for tag in tags.split(",") if tag.strip()])

            cursor.execute("""
                INSERT INTO notes (title, category, subject, description, uploader_id,
                                 tags, file_path, file_name, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, category, subject, description, self.current_user['id'],
                  tags_list, file_path, file_name, file_size))

            conn.commit()
            conn.close()

            return True, f"✅ '{title}' uploaded successfully!"

        except Exception as e:
            return False, f"Error uploading file: {str(e)}"

    def search_notes(self, query: str = "", category: str = "All",
                    sort_by: str = "recent") -> List[Dict]:
        """Search notes with filters"""
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT n.*, u.username as uploader_name,
                   CASE WHEN n.rating_count > 0
                        THEN CAST(n.rating_sum AS FLOAT) / n.rating_count
                        ELSE 0 END as avg_rating
            FROM notes n
            JOIN users u ON n.uploader_id = u.id
            WHERE 1=1
        """
        params = []

        if query:
            sql += """ AND (
                n.title LIKE ? OR
                n.description LIKE ? OR
                n.subject LIKE ? OR
                n.tags LIKE ?
            )"""
            search_term = f"%{query}%"
            params.extend([search_term] * 4)

        if category != "All":
            sql += " AND n.category = ?"
            params.append(category)

        # Sorting
        if sort_by == "recent":
            sql += " ORDER BY n.upload_date DESC"
        elif sort_by == "popular":
            sql += " ORDER BY n.downloads DESC"
        elif sort_by == "rating":
            sql += " ORDER BY avg_rating DESC"

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'title': row['title'],
                'category': row['category'],
                'subject': row['subject'],
                'description': row['description'],
                'uploader_name': row['uploader_name'],
                'upload_date': row['upload_date'],
                'downloads': row['downloads'],
                'tags': json.loads(row['tags']),
                'file_path': row['file_path'],
                'file_name': row['file_name'],
                'file_size': row['file_size'],
                'avg_rating': round(row['avg_rating'], 1)
            })

        return results

    def download_note(self, note_id: int) -> Tuple[bool, str, Optional[str]]:
        """Download note and track download"""
        if not self.current_user:
            return False, "Please login first", None

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        note = cursor.fetchone()

        if not note:
            conn.close()
            return False, "Note not found", None

        # Update download count
        cursor.execute("UPDATE notes SET downloads = downloads + 1 WHERE id = ?", (note_id,))

        # Track download history
        cursor.execute("""
            INSERT INTO download_history (note_id, user_id)
            VALUES (?, ?)
        """, (note_id, self.current_user['id']))

        conn.commit()
        conn.close()

        return True, f"✅ '{note['title']}' ready for download", note['file_path']

    def rate_note(self, note_id: int, rating: int, review: str = "") -> Tuple[bool, str]:
        """Rate a note"""
        if not self.current_user:
            return False, "Please login first"

        if rating < 1 or rating > 5:
            return False, "Rating must be between 1 and 5"

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Insert or update rating
            cursor.execute("""
                INSERT INTO ratings (note_id, user_id, rating, review)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(note_id, user_id)
                DO UPDATE SET rating = ?, review = ?
            """, (note_id, self.current_user['id'], rating, review, rating, review))

            # Update note rating summary
            cursor.execute("""
                UPDATE notes
                SET rating_sum = (SELECT SUM(rating) FROM ratings WHERE note_id = ?),
                    rating_count = (SELECT COUNT(*) FROM ratings WHERE note_id = ?)
                WHERE id = ?
            """, (note_id, note_id, note_id))

            conn.commit()
            conn.close()
            return True, "✅ Rating submitted successfully!"

        except Exception as e:
            conn.close()
            return False, f"Error submitting rating: {str(e)}"

    def get_user_stats(self) -> Dict:
        """Get user statistics"""
        if not self.current_user:
            return {}

        conn = self._get_connection()
        cursor = conn.cursor()

        # User info
        cursor.execute("""
            SELECT username, email, created_at FROM users WHERE id = ?
        """, (self.current_user['id'],))
        user = cursor.fetchone()

        # Upload stats
        cursor.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(downloads), 0) as total_downloads
            FROM notes WHERE uploader_id = ?
        """, (self.current_user['id'],))
        upload_stats = cursor.fetchone()

        # Download stats
        cursor.execute("""
            SELECT COUNT(*) FROM download_history WHERE user_id = ?
        """, (self.current_user['id'],))
        download_count = cursor.fetchone()[0]

        conn.close()

        return {
            'username': user['username'],
            'email': user['email'],
            'member_since': user['created_at'][:10],
            'total_uploads': upload_stats['count'],
            'total_downloads_of_uploads': upload_stats['total_downloads'],
            'personal_downloads': download_count,
            'role': self.current_user['role']
        }

    def get_all_categories(self) -> List[str]:
        """Get all unique categories"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM notes ORDER BY category")
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        return ["All"] + categories

    def delete_note(self, note_id: int) -> Tuple[bool, str]:
        """Delete note (only by uploader or admin)"""
        if not self.current_user:
            return False, "Please login first"

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        note = cursor.fetchone()

        if not note:
            conn.close()
            return False, "Note not found"

        # Check permission
        if note['uploader_id'] != self.current_user['id'] and self.current_user['role'] != 'admin':
            conn.close()
            return False, "You don't have permission to delete this note"

        # Delete file
        try:
            if os.path.exists(note['file_path']):
                os.remove(note['file_path'])
        except:
            pass

        # Delete from database
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        cursor.execute("DELETE FROM download_history WHERE note_id = ?", (note_id,))
        cursor.execute("DELETE FROM ratings WHERE note_id = ?", (note_id,))

        conn.commit()
        conn.close()

        return True, "✅ Note deleted successfully"

# Initialize database
db = NotesDatabase()

# ============================================================================
# UI HELPER FUNCTIONS
# ============================================================================

def format_file_size(size_bytes: int) -> str:
    """Format file size to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def format_note_card(note: Dict) -> str:
    """Format note as beautiful HTML card"""
    tags_html = " ".join([
        f'<span style="background:rgba(102,126,234,0.2);color:#667eea;padding:4px 12px;'
        f'border-radius:20px;font-size:12px;margin-right:6px;font-weight:500;">{tag}</span>'
        for tag in note['tags']
    ])

    file_size = format_file_size(note['file_size'])
    stars = "⭐" * int(note['avg_rating']) + "☆" * (5 - int(note['avg_rating']))

    return f"""
    <div style="background:white;border-radius:20px;padding:28px;margin:16px 0;
                box-shadow:0 10px 30px rgba(0,0,0,0.08);border:1px solid #e8e8e8;
                transition:all 0.3s ease;">
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:16px;">
            <div style="flex:1;">
                <h3 style="margin:0 0 12px 0;font-size:24px;font-weight:700;color:#2d3748;
                           line-height:1.3;">{note['title']}</h3>
                <p style="margin:0 0 16px 0;color:#718096;font-size:15px;line-height:1.6;">
                    {note['description']}</p>
                <div style="margin-bottom:16px;">
                    {tags_html}
                </div>
            </div>
            <div style="text-align:right;margin-left:24px;">
                <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           color:white;padding:12px 20px;border-radius:12px;font-size:14px;
                           font-weight:600;margin-bottom:8px;">
                    {note['category']}
                </div>
                <div style="color:#667eea;font-size:28px;font-weight:700;">
                    {note['avg_rating']}/5
                </div>
                <div style="font-size:12px;color:#a0aec0;">
                    {stars}
                </div>
            </div>
        </div>

        <div style="background:#f7fafc;padding:16px;border-radius:12px;margin-bottom:16px;">
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
                       gap:16px;font-size:13px;color:#4a5568;">
                <div>
                    <div style="color:#a0aec0;margin-bottom:4px;">📚 Subject</div>
                    <div style="font-weight:600;">{note['subject']}</div>
                </div>
                <div>
                    <div style="color:#a0aec0;margin-bottom:4px;">👤 Uploaded by</div>
                    <div style="font-weight:600;">{note['uploader_name']}</div>
                </div>
                <div>
                    <div style="color:#a0aec0;margin-bottom:4px;">📅 Date</div>
                    <div style="font-weight:600;">{note['upload_date'][:10]}</div>
                </div>
                <div>
                    <div style="color:#a0aec0;margin-bottom:4px;">⬇️ Downloads</div>
                    <div style="font-weight:600;">{note['downloads']}</div>
                </div>
                <div>
                    <div style="color:#a0aec0;margin-bottom:4px;">📄 File Size</div>
                    <div style="font-weight:600;">{file_size}</div>
                </div>
            </div>
        </div>

        <div style="display:flex;gap:12px;align-items:center;">
            <button onclick="navigator.clipboard.writeText('{note['id']}')"
                    style="background:#667eea;border:none;color:white;padding:12px 24px;
                           border-radius:10px;cursor:pointer;font-weight:600;font-size:14px;
                           transition:all 0.3s ease;">
                📋 Copy ID: {note['id']}
            </button>
            <div style="color:#a0aec0;font-size:13px;font-style:italic;">
                Use this ID to download or rate the note
            </div>
        </div>
    </div>
    """

def create_stats_card(label: str, value: str, icon: str, color: str) -> str:
    """Create statistics card"""
    return f"""
    <div style="background:linear-gradient(135deg, {color}1a 0%, {color}33 100%);
                border-radius:16px;padding:28px;text-align:center;
                border:2px solid {color}40;transition:all 0.3s ease;">
        <div style="font-size:42px;margin-bottom:12px;">{icon}</div>
        <div style="font-size:36px;font-weight:700;margin:12px 0;color:{color};">{value}</div>
        <div style="font-size:15px;color:#4a5568;font-weight:500;">{label}</div>
    </div>
    """

# ============================================================================
# AUTHENTICATION FUNCTIONS
# ============================================================================

def login(username: str, password: str):
    """Handle login"""
    success, message, user_id = db.authenticate(username, password)
    if success:
        categories = db.get_all_categories()
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            f"✅ {message}",
            gr.update(visible=True),
            gr.update(choices=categories, value="All"),
            "",
            ""
        )
    return (
        gr.update(visible=True),
        gr.update(visible=False),
        f"❌ {message}",
        gr.update(visible=False),
        gr.update(),
        username,
        password
    )

def register(username: str, password: str, email: str):
    """Handle registration"""
    success, message = db.register_user(username, password, email)
    if success:
        return f"✅ {message}", "", "", ""
    return f"❌ {message}", username, password, email

def logout():
    """Handle logout"""
    db.current_user = None
    return (
        gr.update(visible=True),
        gr.update(visible=False),
        "",
        gr.update(visible=False),
        gr.update(choices=["All"])
    )

# ============================================================================
# NOTES FUNCTIONS
# ============================================================================

def upload_note(title: str, category: str, subject: str, description: str, tags: str, file):
    """Handle note upload"""
    success, message = db.add_note(title, category, subject, description, tags, file)
    if success:
        # Refresh categories
        categories = db.get_all_categories()
        return (
            message,
            "", "", "", "", "", None,
            gr.update(choices=categories)
        )
    return (
        message,
        title, category, subject, description, tags, file,
        gr.update()
    )

def search_and_display(query: str, category: str, sort_by: str):
    """Search and display notes"""
    results = db.search_notes(query, category, sort_by)

    if not results:
        return """
        <div style="text-align:center;padding:80px 40px;">
            <div style="font-size:64px;margin-bottom:20px;">📭</div>
            <h3 style="color:#4a5568;margin:0 0 12px 0;">No notes found</h3>
            <p style="color:#a0aec0;margin:0;">Try different keywords or category filters</p>
        </div>
        """

    html = f"""
    <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               color:white;padding:24px 32px;border-radius:16px;margin-bottom:24px;">
        <h2 style="margin:0 0 8px 0;font-size:28px;font-weight:700;">
            📚 Found {len(results)} Note{'' if len(results) == 1 else 's'}
        </h2>
        <p style="margin:0;opacity:0.9;font-size:15px;">
            Browse and download study materials shared by your peers
        </p>
    </div>
    """

    for note in results:
        html += format_note_card(note)

    return html

def download_note_by_id(note_id: str):
    """Handle note download"""
    try:
        note_id_int = int(note_id)
        success, message, file_path = db.download_note(note_id_int)
        if success:
            return message, file_path
        return f"❌ {message}", None
    except ValueError:
        return "❌ Invalid note ID. Please enter a number.", None

def rate_note_by_id(note_id: str, rating: int, review: str):
    """Handle note rating"""
    try:
        note_id_int = int(note_id)
        success, message = db.rate_note(note_id_int, rating, review)
        if success:
            return f"{message}", "", 3, ""
        return f"❌ {message}", note_id, rating, review
    except ValueError:
        return "❌ Invalid note ID. Please enter a number.", note_id, rating, review

def show_user_profile():
    """Display user profile"""
    stats = db.get_user_stats()
    if not stats:
        return "<p style='text-align:center;color:#a0aec0;padding:40px;'>Please login to view profile</p>"

    role_badge = {
        'student': ('🎓', '#667eea'),
        'teacher': ('👨‍🏫', '#48bb78'),
        'admin': ('⚡', '#f56565')
    }.get(stats['role'], ('👤', '#667eea'))

    profile_html = f"""
    <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius:20px;padding:40px;color:white;margin-bottom:32px;
                box-shadow:0 20px 40px rgba(102,126,234,0.3);">
        <div style="display:flex;align-items:center;gap:24px;margin-bottom:32px;">
            <div style="background:white;width:100px;height:100px;border-radius:50%;
                       display:flex;align-items:center;justify-content:center;
                       font-size:48px;box-shadow:0 10px 20px rgba(0,0,0,0.2);">
                {role_badge[0]}
            </div>
            <div style="flex:1;">
                <h2 style="margin:0 0 8px 0;font-size:32px;font-weight:700;">
                    {stats['username']}
                </h2>
                <p style="margin:0 0 4px 0;font-size:16px;opacity:0.95;">
                    📧 {stats['email']}
                </p>
                <p style="margin:0;font-size:14px;opacity:0.85;">
                    📅 Member since {stats['member_since']}
                </p>
            </div>
        </div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
               gap:20px;margin-top:32px;">
        {create_stats_card("Notes Uploaded", str(stats['total_uploads']), "📤", "#667eea")}
        {create_stats_card("Downloads Received", str(stats['total_downloads_of_uploads']), "⬇️", "#48bb78")}
        {create_stats_card("Notes Downloaded", str(stats['personal_downloads']), "📥", "#f56565")}
    </div>
    """
    return profile_html

def delete_note_by_id(note_id: str):
    """Handle note deletion"""
    try:
        note_id_int = int(note_id)
        success, message = db.delete_note(note_id_int)
        if success:
            return f"{message}", ""
        return f"❌ {message}", note_id
    except ValueError:
        return "❌ Invalid note ID. Please enter a number.", note_id

# ============================================================================
# GRADIO INTERFACE
# ============================================================================

custom_css = """
.gradio-container {
    max-width: 1400px !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 48px;
    border-radius: 24px;
    text-align: center;
    margin-bottom: 40px;
    box-shadow: 0 20px 60px rgba(102, 126, 234, 0.3);
}

.tabs {
    border-radius: 16px;
    overflow: hidden;
}

button {
    transition: all 0.3s ease !important;
}

button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 16px rgba(0,0,0,0.2) !important;
}

.gr-button-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important;
    font-weight: 600 !important;
}

.gr-button-secondary {
    background: #f7fafc !important;
    border: 2px solid #e2e8f0 !important;
    color: #4a5568 !important;
    font-weight: 600 !important;
}

.gr-input, .gr-text, .gr-dropdown {
    border-radius: 12px !important;
    border: 2px solid #e2e8f0 !important;
}

.gr-input:focus, .gr-text:focus, .gr-dropdown:focus {
    border-color: #667eea !important;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
}

.gr-form {
    gap: 16px !important;
}

.gr-box {
    border-radius: 16px !important;
}
"""

with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as app:

    # Header
    gr.HTML("""
        <div class="main-header">
            <h1 style="margin:0;font-size:56px;font-weight:800;letter-spacing:-1px;">
                ☁️ CloudNotes Pro
            </h1>
            <p style="margin:16px 0 0 0;font-size:20px;opacity:0.95;font-weight:400;">
                Advanced Cloud-Powered Academic Notes Sharing Platform
            </p>
            <div style="margin-top:24px;display:flex;gap:24px;justify-content:center;
                       font-size:14px;opacity:0.9;">
                <span>🔐 Secure Authentication</span>
                <span>💾 Real File Storage</span>
                <span>🔍 Advanced Search</span>
                <span>⭐ Rating System</span>
            </div>
        </div>
    """)

    # Login/Register Section
    with gr.Row(visible=True) as login_section:
        with gr.Column(scale=1):
            gr.HTML("""
                <div style="text-align:center;padding:40px 20px;">
                    <div style="font-size:80px;margin-bottom:20px;">📚</div>
                    <h2 style="color:#667eea;margin:0 0 12px 0;">Welcome to CloudNotes</h2>
                    <p style="color:#718096;margin:0;">Share knowledge, build community</p>
                </div>
            """)

        with gr.Column(scale=1):
            with gr.Tabs():
                with gr.Tab("🔐 Login"):
                    gr.Markdown("### Sign in to your account")
                    login_username = gr.Textbox(
                        label="Username",
                        placeholder="Enter your username",
                        info="Use 'admin', 'student1', or 'professor' for demo"
                    )
                    login_password = gr.Textbox(
                        label="Password",
                        type="password",
                        placeholder="Enter your password",
                        info="Default password: 'admin123', 'pass123', or 'prof123'"
                    )
                    login_btn = gr.Button("🚀 Login", variant="primary", size="lg")
                    login_status = gr.Markdown()

                    gr.Markdown("""
                    ---
                    **📝 Demo Accounts:**
                    - 👨‍💼 Admin: `admin` / `admin123`
                    - 🎓 Student: `student1` / `pass123`
                    - 👨‍🏫 Professor: `professor` / `prof123`
                    """)

                with gr.Tab("📝 Register"):
                    gr.Markdown("### Create a new account")
                    reg_username = gr.Textbox(
                        label="Username",
                        placeholder="Choose a unique username (min 3 chars)"
                    )
                    reg_email = gr.Textbox(
                        label="Email",
                        placeholder="your.email@university.edu"
                    )
                    reg_password = gr.Textbox(
                        label="Password",
                        type="password",
                        placeholder="Choose a strong password (min 6 chars)"
                    )
                    reg_btn = gr.Button("✨ Create Account", variant="primary", size="lg")
                    reg_status = gr.Markdown()

    # Main Application
    with gr.Column(visible=False) as main_app:

        with gr.Row():
            gr.HTML("""
                <div style="flex:1;"></div>
            """)
            logout_btn = gr.Button("🚪 Logout", variant="secondary", size="sm", visible=False)

        with gr.Tabs() as tabs:
            # Browse & Search Tab
            with gr.Tab("🔍 Browse Notes"):
                gr.Markdown("### 📚 Discover and download study materials")

                with gr.Row():
                    search_query = gr.Textbox(
                        label="Search",
                        placeholder="🔍 Search by title, subject, tags, or description...",
                        scale=3
                    )
                    search_category = gr.Dropdown(
                        choices=["All"],
                        value="All",
                        label="Category",
                        scale=1
                    )
                    sort_by = gr.Dropdown(
                        choices=[
                            ("Most Recent", "recent"),
                            ("Most Popular", "popular"),
                            ("Highest Rated", "rating")
                        ],
                        value="recent",
                        label="Sort By",
                        scale=1
                    )

                search_btn = gr.Button("🔍 Search Notes", variant="primary", size="lg")

                search_results = gr.HTML()

                # Auto-load all notes on tab open
                tabs.select(
                    fn=lambda: search_and_display("", "All", "recent"),
                    outputs=[search_results]
                )

            # Upload Tab
            with gr.Tab("📤 Upload Notes"):
                gr.Markdown("### 📝 Share your study materials with the community")

                with gr.Row():
                    with gr.Column():
                        upload_title = gr.Textbox(
                            label="Note Title *",
                            placeholder="e.g., Linear Algebra Chapter 3 - Eigenvalues"
                        )
                        upload_category = gr.Dropdown(
                            choices=[
                                "Computer Science", "Mathematics", "Physics",
                                "Chemistry", "Biology", "Engineering",
                                "Literature", "History", "Economics", "Business"
                            ],
                            label="Category *"
                        )
                        upload_subject = gr.Textbox(
                            label="Subject *",
                            placeholder="e.g., Linear Algebra, Organic Chemistry"
                        )

                    with gr.Column():
                        upload_desc = gr.Textbox(
                            label="Description",
                            lines=4,
                            placeholder="Provide a detailed description of what's covered in these notes..."
                        )
                        upload_tags = gr.Textbox(
                            label="Tags (comma-separated)",
                            placeholder="e.g., algebra, matrices, eigenvalues, linear-transformations"
                        )

                upload_file = gr.File(
                    label="📎 Upload File (PDF, DOC, DOCX, TXT)",
                    file_types=[".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx"]
                )

                upload_btn = gr.Button("📤 Upload Note", variant="primary", size="lg")
                upload_status = gr.Markdown()

            # Download Tab
            with gr.Tab("⬇️ Download Notes"):
                gr.Markdown("### 💾 Download notes directly to your device")

                gr.HTML("""
                    <div style="background:#eef2ff;border-left:4px solid #667eea;
                               padding:20px;border-radius:12px;margin:20px 0;">
                        <strong style="color:#667eea;">💡 How to Download:</strong>
                        <ol style="margin:12px 0 0 0;color:#4a5568;">
                            <li>Browse notes in the "Browse Notes" tab</li>
                            <li>Copy the Note ID from the note card</li>
                            <li>Paste it below and click Download</li>
                        </ol>
                    </div>
                """)

                with gr.Row():
                    download_id = gr.Textbox(
                        label="Note ID",
                        placeholder="Enter the note ID (e.g., 1, 2, 3...)",
                        scale=3
                    )
                    download_btn = gr.Button("⬇️ Download", variant="primary", size="lg", scale=1)

                download_status = gr.Markdown()
                download_file = gr.File(label="Downloaded File", visible=True)

            # Rate Notes Tab
            with gr.Tab("⭐ Rate Notes"):
                gr.Markdown("### 📊 Share your feedback and rate notes")

                gr.HTML("""
                    <div style="background:#fff7ed;border-left:4px solid #f59e0b;
                               padding:20px;border-radius:12px;margin:20px 0;">
                        <strong style="color:#f59e0b;">⭐ Help the Community:</strong>
                        <p style="margin:8px 0 0 0;color:#4a5568;">
                            Your ratings help other students find quality study materials.
                            Rate notes you've downloaded and leave helpful reviews!
                        </p>
                    </div>
                """)

                with gr.Row():
                    with gr.Column(scale=2):
                        rate_note_id = gr.Textbox(
                            label="Note ID",
                            placeholder="Enter the note ID you want to rate"
                        )
                        rating_slider = gr.Slider(
                            minimum=1,
                            maximum=5,
                            step=1,
                            value=3,
                            label="Rating (1-5 stars)",
                            info="1 = Poor, 5 = Excellent"
                        )
                        review_text = gr.Textbox(
                            label="Review (Optional)",
                            lines=3,
                            placeholder="Share your thoughts about these notes..."
                        )
                        rate_btn = gr.Button("⭐ Submit Rating", variant="primary", size="lg")
                        rate_status = gr.Markdown()

            # My Profile Tab
            with gr.Tab("👤 My Profile"):
                gr.Markdown("### 📊 Your Statistics and Activity")

                profile_display = gr.HTML()

                with gr.Row():
                    refresh_profile_btn = gr.Button("🔄 Refresh Profile", variant="secondary")

                gr.Markdown("---")
                gr.Markdown("### 🗑️ Delete Your Notes")

                with gr.Row():
                    delete_note_id = gr.Textbox(
                        label="Note ID to Delete",
                        placeholder="Enter the ID of your note to delete",
                        scale=3
                    )
                    delete_btn = gr.Button("🗑️ Delete", variant="stop", scale=1)

                delete_status = gr.Markdown()

                # Auto-load profile
                tabs.select(
                    fn=show_user_profile,
                    outputs=[profile_display]
                )

    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================

    # Authentication
    login_btn.click(
        login,
        inputs=[login_username, login_password],
        outputs=[login_section, main_app, login_status, logout_btn,
                search_category, login_username, login_password]
    )

    reg_btn.click(
        register,
        inputs=[reg_username, reg_password, reg_email],
        outputs=[reg_status, reg_username, reg_password, reg_email]
    )

    logout_btn.click(
        logout,
        outputs=[login_section, main_app, login_status, logout_btn, search_category]
    )

    # Search
    search_btn.click(
        search_and_display,
        inputs=[search_query, search_category, sort_by],
        outputs=[search_results]
    )

    # Also trigger search on Enter key
    search_query.submit(
        search_and_display,
        inputs=[search_query, search_category, sort_by],
        outputs=[search_results]
    )

    # Upload
    upload_btn.click(
        upload_note,
        inputs=[upload_title, upload_category, upload_subject,
               upload_desc, upload_tags, upload_file],
        outputs=[upload_status, upload_title, upload_category,
                upload_subject, upload_desc, upload_tags, upload_file,
                search_category]
    )

    # Download
    download_btn.click(
        download_note_by_id,
        inputs=[download_id],
        outputs=[download_status, download_file]
    )

    # Rate
    rate_btn.click(
        rate_note_by_id,
        inputs=[rate_note_id, rating_slider, review_text],
        outputs=[rate_status, rate_note_id, rating_slider, review_text]
    )

    # Profile
    refresh_profile_btn.click(
        show_user_profile,
        outputs=[profile_display]
    )

    # Delete
    delete_btn.click(
        delete_note_by_id,
        inputs=[delete_note_id],
        outputs=[delete_status, delete_note_id]
    )

    # Initial load
    app.load(
        fn=lambda: search_and_display("", "All", "recent"),
        outputs=[search_results]
    )

# Launch the application
if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=10000,
        share=False
    )
