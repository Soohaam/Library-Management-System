import sqlite3
from datetime import datetime

DATABASE = 'library.db'


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database with tables"""
    conn = get_db()
    cursor = conn.cursor()

    # Create Books table
    cursor.execute('''CREATE TABLE IF NOT EXISTS books (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        authors TEXT,
                        publisher TEXT,
                        isbn TEXT UNIQUE,
                        isbn13 TEXT,
                        num_pages INTEGER,
                        stock INTEGER DEFAULT 0,
                        available INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

    # Create Members table
    cursor.execute('''CREATE TABLE IF NOT EXISTS members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        phone TEXT,
                        debt REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

    # Create Transactions table
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        member_id INTEGER NOT NULL,
                        issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        return_date TIMESTAMP,
                        fee REAL DEFAULT 0,
                        status TEXT DEFAULT 'issued',
                        FOREIGN KEY (book_id) REFERENCES books(id),
                        FOREIGN KEY (member_id) REFERENCES members(id)
                    )''')

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


# ---------------------- BOOK OPERATIONS ----------------------

def add_book(title, authors, publisher, isbn, isbn13, num_pages, stock):
    """Add a new book to the database"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''INSERT INTO books (title, authors, publisher, isbn, isbn13, num_pages, stock, available)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                       (title, authors, publisher, isbn, isbn13, num_pages, stock, stock))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Book already exists, update stock
        cursor.execute('''UPDATE books SET stock = stock + ?, available = available + ?
                          WHERE isbn = ?''', (stock, stock, isbn))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_all_books():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM books ORDER BY title')
    books = cursor.fetchall()
    conn.close()
    return books


def get_book(book_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM books WHERE id = ?', (book_id,))
    book = cursor.fetchone()
    conn.close()
    return book


def update_book(book_id, title, authors, publisher, isbn, stock):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''UPDATE books SET title = ?, authors = ?, publisher = ?, isbn = ?, stock = ?
                      WHERE id = ?''', (title, authors, publisher, isbn, stock, book_id))
    conn.commit()
    conn.close()


def delete_book(book_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM books WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()


def search_books(query):
    conn = get_db()
    cursor = conn.cursor()
    search_query = f'%{query}%'
    cursor.execute('''SELECT * FROM books 
                      WHERE title LIKE ? OR authors LIKE ?
                      ORDER BY title''', (search_query, search_query))
    books = cursor.fetchall()
    conn.close()
    return books


# ---------------------- MEMBER OPERATIONS ----------------------

def add_member(name, email, phone):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO members (name, email, phone) VALUES (?, ?, ?)',
                       (name, email, phone))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_all_members():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM members ORDER BY name')
    members = cursor.fetchall()
    conn.close()
    return members


def get_member(member_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM members WHERE id = ?', (member_id,))
    member = cursor.fetchone()
    conn.close()
    return member


def update_member(member_id, name, email, phone):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE members SET name = ?, email = ?, phone = ? WHERE id = ?',
                   (name, email, phone, member_id))
    conn.commit()
    conn.close()


def delete_member(member_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM members WHERE id = ?', (member_id,))
    conn.commit()
    conn.close()


# ---------------------- TRANSACTION OPERATIONS ----------------------

def issue_book(book_id, member_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if book is available
    cursor.execute('SELECT available FROM books WHERE id = ?', (book_id,))
    book = cursor.fetchone()
    if not book or book['available'] <= 0:
        conn.close()
        return False, "Book not available"
    
    # Check member debt
    cursor.execute('SELECT debt FROM members WHERE id = ?', (member_id,))
    member = cursor.fetchone()
    if not member:
        conn.close()
        return False, "Member not found"
    
    if member['debt'] >= 500:
        conn.close()
        return False, "Member has outstanding debt of Rs.500 or more"
    
    # Issue the book
    cursor.execute('INSERT INTO transactions (book_id, member_id, status) VALUES (?, ?, ?)',
                   (book_id, member_id, 'issued'))
    cursor.execute('UPDATE books SET available = available - 1 WHERE id = ?', (book_id,))
    
    conn.commit()
    conn.close()
    return True, "Book issued successfully"


def return_book(transaction_id, fee):
    conn = get_db()
    cursor = conn.cursor()
    
    # Get transaction details
    cursor.execute('''SELECT t.*, b.id as book_id, m.id as member_id 
                      FROM transactions t
                      JOIN books b ON t.book_id = b.id
                      JOIN members m ON t.member_id = m.id
                      WHERE t.id = ? AND t.status = 'issued' ''', (transaction_id,))
    transaction = cursor.fetchone()
    
    if not transaction:
        conn.close()
        return False, "Transaction not found or already returned"
    
    # Update transaction
    cursor.execute('''UPDATE transactions 
                      SET return_date = CURRENT_TIMESTAMP, fee = ?, status = 'returned'
                      WHERE id = ?''', (fee, transaction_id))
    
    # Update book availability
    cursor.execute('UPDATE books SET available = available + 1 WHERE id = ?',
                   (transaction['book_id'],))
    
    # Update member debt
    cursor.execute('UPDATE members SET debt = debt + ? WHERE id = ?',
                   (fee, transaction['member_id']))
    
    conn.commit()
    conn.close()
    return True, "Book returned successfully"


def get_all_transactions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''SELECT t.*, b.title as book_title, m.name as member_name
                      FROM transactions t
                      JOIN books b ON t.book_id = b.id
                      JOIN members m ON t.member_id = m.id
                      ORDER BY t.issue_date DESC''')
    transactions = cursor.fetchall()
    conn.close()
    return transactions


def get_issued_books():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''SELECT t.*, b.title as book_title, b.authors, m.name as member_name, m.email
                      FROM transactions t
                      JOIN books b ON t.book_id = b.id
                      JOIN members m ON t.member_id = m.id
                      WHERE t.status = 'issued'
                      ORDER BY t.issue_date DESC''')
    transactions = cursor.fetchall()
    conn.close()
    return transactions


def get_member_transactions(member_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''SELECT t.*, b.title as book_title
                      FROM transactions t
                      JOIN books b ON t.book_id = b.id
                      WHERE t.member_id = ?
                      ORDER BY t.issue_date DESC''', (member_id,))
    transactions = cursor.fetchall()
    conn.close()
    return transactions