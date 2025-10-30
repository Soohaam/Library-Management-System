from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests
from database import *

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# Initialize database on startup
with app.app_context():
    init_db()

# --- HOME PAGE ---
@app.route('/')
def index():
    stats = {
        'total_books': len(get_all_books()),
        'total_members': len(get_all_members()),
        'issued_books': len(get_issued_books()),
        'total_transactions': len(get_all_transactions())
    }
    return render_template('index.html', stats=stats)

# --- BOOKS ROUTES ---
@app.route('/books')
def books():
    all_books = get_all_books()
    return render_template('books.html', books=all_books)

@app.route('/books/add', methods=['POST'])
def add_book_route():
    data = request.form
    book_id = add_book(
        data['title'],
        data['authors'],
        data.get('publisher', ''),
        data.get('isbn', ''),
        data.get('isbn13', ''),
        int(data.get('num_pages', 0)),
        int(data['stock'])
    )
    flash('Book added successfully!', 'success')
    return redirect(url_for('books'))

@app.route('/books/update/<int:book_id>', methods=['POST'])
def update_book_route(book_id):
    data = request.form
    update_book(
        book_id,
        data['title'],
        data['authors'],
        data['publisher'],
        data['isbn'],
        int(data['stock'])
    )
    flash('Book updated successfully!', 'success')
    return redirect(url_for('books'))

@app.route('/books/delete/<int:book_id>', methods=['POST'])
def delete_book_route(book_id):
    delete_book(book_id)
    flash('Book deleted successfully!', 'success')
    return redirect(url_for('books'))

@app.route('/books/search')
def search_books_route():
    query = request.args.get('q', '')
    if query:
        books_list = search_books(query)
        return render_template('books.html', books=books_list, search_query=query)
    return redirect(url_for('books'))

# --- MEMBERS ROUTES ---
@app.route('/members')
def members():
    all_members = get_all_members()
    return render_template('members.html', members=all_members)

@app.route('/members/add', methods=['POST'])
def add_member_route():
    data = request.form
    member_id = add_member(data['name'], data['email'], data.get('phone', ''))
    if member_id:
        flash('Member added successfully!', 'success')
    else:
        flash('Email already exists!', 'error')
    return redirect(url_for('members'))

@app.route('/members/update/<int:member_id>', methods=['POST'])
def update_member_route(member_id):
    data = request.form
    update_member(member_id, data['name'], data['email'], data.get('phone', ''))
    flash('Member updated successfully!', 'success')
    return redirect(url_for('members'))

@app.route('/members/delete/<int:member_id>', methods=['POST'])
def delete_member_route(member_id):
    delete_member(member_id)
    flash('Member deleted successfully!', 'success')
    return redirect(url_for('members'))

# --- TRANSACTIONS ROUTES ---
@app.route('/transactions')
def transactions():
    all_transactions = get_all_transactions()
    issued = get_issued_books()
    all_books = get_all_books()
    all_members = get_all_members()
    return render_template('transactions.html', 
                         transactions=all_transactions,
                         issued_books=issued,
                         books=all_books,
                         members=all_members)

@app.route('/transactions/issue', methods=['POST'])
def issue_book_route():
    data = request.form
    success, message = issue_book(int(data['book_id']), int(data['member_id']))
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('transactions'))

@app.route('/transactions/return/<int:transaction_id>', methods=['POST'])
def return_book_route(transaction_id):
    fee = float(request.form.get('fee', 0))
    success, message = return_book(transaction_id, fee)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('transactions'))

# --- IMPORT BOOKS FROM FRAPPE API ---
@app.route('/import')
def import_books_page():
    return render_template('import_books.html')

@app.route('/import/books', methods=['POST'])
def import_books_route():
    data = request.form
    num_books = int(data.get('num_books', 20))
    title = data.get('title', '')
    authors = data.get('authors', '')
    isbn = data.get('isbn', '')
    publisher = data.get('publisher', '')
    
    imported_count = 0
    page = 1
    
    try:
        while imported_count < num_books:
            # Build API URL with parameters
            api_url = f'https://frappe.io/api/method/frappe-library?page={page}'
            if title:
                api_url += f'&title={title}'
            if authors:
                api_url += f'&authors={authors}'
            if isbn:
                api_url += f'&isbn={isbn}'
            if publisher:
                api_url += f'&publisher={publisher}'
            
            # Fetch data from API
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            books_data = response.json()
            if 'message' not in books_data or not books_data['message']:
                break
            
            # Import books
            for book in books_data['message']:
                if imported_count >= num_books:
                    break
                
                add_book(
                    title=book.get('title', 'Unknown'),
                    authors=book.get('authors', 'Unknown'),
                    publisher=book.get('publisher', ''),
                    isbn=book.get('isbn', ''),
                    isbn13=book.get('isbn13', ''),
                    num_pages=int(book.get('num_pages', 0)),
                    stock=1  # Add 1 copy of each book
                )
                imported_count += 1
            
            page += 1
            
            # Safety check to avoid infinite loop
            if page > 100:
                break
        
        flash(f'Successfully imported {imported_count} books!', 'success')
    except Exception as e:
        flash(f'Error importing books: {str(e)}', 'error')
    
    return redirect(url_for('import_books_page'))

# --- REPORTS ---
@app.route('/reports')
def reports():
    all_books = get_all_books()
    all_members = get_all_members()
    issued = get_issued_books()
    
    # High debt members
    high_debt_members = [m for m in all_members if m['debt'] > 100]
    
    # Popular books (most issued)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''SELECT b.title, b.authors, COUNT(t.id) as issue_count
                      FROM books b
                      LEFT JOIN transactions t ON b.id = t.book_id
                      GROUP BY b.id
                      HAVING issue_count > 0
                      ORDER BY issue_count DESC
                      LIMIT 10''')
    popular_books = cursor.fetchall()
    conn.close()
    
    return render_template('reports.html',
                         books=all_books,
                         members=all_members,
                         issued_books=issued,
                         high_debt_members=high_debt_members,
                         popular_books=popular_books)

# --- API ENDPOINTS (for AJAX) ---
@app.route('/api/books')
def api_books():
    books_list = get_all_books()
    return jsonify([dict(book) for book in books_list])

@app.route('/api/members')
def api_members():
    members_list = get_all_members()
    return jsonify([dict(member) for member in members_list])

@app.route('/api/book/<int:book_id>')
def api_book(book_id):
    book = get_book(book_id)
    if book:
        return jsonify(dict(book))
    return jsonify({'error': 'Book not found'}), 404

@app.route('/api/member/<int:member_id>')
def api_member(member_id):
    member = get_member(member_id)
    if member:
        return jsonify(dict(member))
    return jsonify({'error': 'Member not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)