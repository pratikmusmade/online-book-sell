from flask import Flask, render_template, request, redirect, url_for, session,flash

from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
import os
from werkzeug.utils import secure_filename
app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'  # Folder to store images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Secret key for session management
app.secret_key = 'b9a8f3e2d5c7a1b49e3f7d2c8a6e5b1c3f2d9e4b7a1c5e2f6d3b8a9c4e7f6d2a'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'ecom_books'

mysql = MySQL(app)

# Hardcoded admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin@123'

@app.route('/')
def home():
    return render_template('login.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/register', methods=['GET', 'POST'])
def registerUser():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']  # ✅ Get email from form
        password = request.form['password']
        phone = request.form['phone_number'] 

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Check if the email or username already exists
        cursor.execute('SELECT * FROM users WHERE username = %s OR email = %s', (username, email))
        account = cursor.fetchone()

        if account:
            flash('Username or email already exists!', 'danger')
        else:
            # Insert new user into the database
            cursor.execute('INSERT INTO users (username, email, password, phone_number) VALUES (%s, %s, %s, %s)', 
                           (username, email, password, phone))
            mysql.connection.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))

        cursor.close()

    return render_template('register.html')


    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Check if username and password are provided
        if 'username' not in request.form or 'password' not in request.form:
            flash("Please fill out both fields!", "danger")
            return redirect(url_for('login'))

        username = request.form['username']
        password = request.form['password']

        # Check if the user is the admin (hardcoded credentials)
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['loggedin'] = True
            session['username'] = username
            session['role'] = 'admin'
            flash("Admin login successful!", "success")
            return redirect(url_for('admin_dashboard'))
        
        # Authenticate normal users from database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT id, username FROM users WHERE username = %s AND password = %s', (username, password))
        account = cursor.fetchone()

        if account:
            session['loggedin'] = True
            session['user_id'] = account['id']  # ✅ Store user ID
            session['username'] = account['username']
            session['role'] = 'user'
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Incorrect username or password!", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'loggedin' not in session:
        flash('Please log in first!', 'warning')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch recent purchases
    cursor.execute("""
        SELECT p.*, b.title, b.author FROM purchases p
        JOIN books b ON p.book_id = b.id
        WHERE p.buyer_id = %s
        ORDER BY p.purchase_date DESC
        """, (session['user_id'],))
    purchases = cursor.fetchall()

    # Fetch books listed for sale by the user
    cursor.execute("SELECT * FROM books WHERE seller_id = %s", (session['user_id'],))
    books_for_sale = cursor.fetchall()

    cursor.close()

    return render_template('dashboard.html', purchases=purchases, books_for_sale=books_for_sale)


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all purchase requests
    cursor.execute("""
        SELECT p.id, p.status, p.paid, p.purchase_date, p.price,
               b.title AS book_title, u.username AS buyer_name, u.phone_number
        FROM purchases p
        JOIN books b ON p.book_id = b.id
        JOIN users u ON p.buyer_id = u.id
        ORDER BY p.purchase_date DESC
    """)
    purchases = cursor.fetchall()
    cursor.close()

    return render_template('admin_dashboard.html', purchases=purchases)


@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

# Function to check if user is logged in and their role
def get_user_role():
    if 'loggedin' in session:
        return session.get('role')
    return None




@app.route('/books')
def books():
    print(url_for('books'))
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM books")  # Ensure the table name matches your database
    books = cursor.fetchall()
    cursor.close()
    return render_template('books.html', books=books)

@app.route('/book/<int:book_id>')
def book_detail(book_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM books WHERE id = %s', (book_id,))
    book = cursor.fetchone()
    cursor.close()

    if not book:
        flash('Book not found!', 'danger')
        return redirect(url_for('books'))

    return render_template('book_detail.html', book=book)





@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if 'loggedin' not in session or 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        price = request.form['price']
        seller_id = session['user_id']

        # Handle Image Upload
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
            else:
                filename = 'default.jpg'
        else:
            filename = 'default.jpg'

        # Insert into database
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO books (title, author, price, seller_id, image) VALUES (%s, %s, %s, %s, %s)",
                       (title, author, price, seller_id, filename))
        mysql.connection.commit()
        cursor.close()

        flash("Book added successfully!", "success")  # ✅ Flash success message
        return redirect(url_for('add_book'))  # ✅ Reload page

    return render_template('add_book.html')


@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    if 'loggedin' not in session:
        flash('Please log in first!', 'warning')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch book details
    cursor.execute("SELECT * FROM books WHERE id = %s AND seller_id = %s", (book_id, session['user_id']))
    book = cursor.fetchone()

    if not book:
        flash("Book not found or you don't have permission to edit it.", 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        price = request.form['price']

        cursor.execute("UPDATE books SET title = %s, author = %s, price = %s WHERE id = %s", 
                       (title, author, price, book_id))
        mysql.connection.commit()
        cursor.close()

        flash('Book updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    cursor.close()
    return render_template('edit_book.html', book=book)

@app.route('/delete_book/<int:book_id>', methods=['GET','POST'])
def delete_book(book_id):
    if 'loggedin' not in session:
        flash('Please log in first!', 'warning')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Ensure user owns the book before deleting
    cursor.execute("SELECT * FROM books WHERE id = %s AND seller_id = %s", (book_id, session['user_id']))
    book = cursor.fetchone()

    if not book:
        flash("Book not found or you don't have permission to delete it.", 'danger')
        return redirect(url_for('dashboard'))

    cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
    mysql.connection.commit()
    cursor.close()

    flash('Book deleted successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/my_purchases')
def my_purchases():
    if 'loggedin' not in session:
        flash('Please log in to view your purchases.', 'danger')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ✅ Fetch purchased books with status and payment info
    cursor.execute('''
        SELECT b.title, b.author, p.price, p.status, p.paid, u.username AS seller_name
        FROM purchases p
        JOIN books b ON p.book_id = b.id
        JOIN users u ON p.seller_id = u.id
        WHERE p.buyer_id = %s
        ORDER BY p.purchase_date DESC
    ''', (session['user_id'],))

    purchased_books = cursor.fetchall()
    cursor.close()

    return render_template('my_purchases.html', purchased_books=purchased_books)



@app.route('/buy_book/<int:book_id>', methods=['GET','POST'])
def buy_book(book_id):
    if 'loggedin' not in session:
        flash('Please log in to buy books.', 'danger')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ✅ Fetch book details
    cursor.execute('SELECT * FROM books WHERE id = %s', (book_id,))
    book = cursor.fetchone()

    if not book:
        flash('Book not found!', 'danger')
        return redirect(url_for('books'))

    # ✅ Prevent self-purchase
    if session['user_id'] == book['seller_id']:
        flash("You can't buy your own book!", 'warning')
        return redirect(url_for('books'))

    # ✅ Insert into purchases table
    cursor.execute('''
        INSERT INTO purchases (book_id, buyer_id, seller_id, price)
        VALUES (%s, %s, %s, %s)
    ''', (book_id, session['user_id'], book['seller_id'], book['price']))
    mysql.connection.commit()

    flash('Purchase successful! Admin will contact you shortly.', 'success')
    return redirect(url_for('books'))

@app.route('/admin/buy_requests')
def admin_buy_requests():
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch all purchase requests with book and buyer info
    cursor.execute("""
        SELECT p.id, b.title, b.price, u.username AS buyer_name, u.phone_number, p.status, p.paid
        FROM purchases p
        JOIN books b ON p.book_id = b.id
        JOIN users u ON p.buyer_id = u.id
        ORDER BY p.purchase_date DESC
    """)
    
    purchases = cursor.fetchall()
    cursor.close()

    return render_template('admin_buy_requests.html', purchases=purchases)


@app.route('/admin/buy_request/<int:purchase_id>')
def admin_buy_request_details(purchase_id):
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch full details of a single purchase request
    cursor.execute("""
        SELECT p.id, b.title, b.author, b.price, u.username AS buyer_name, 
               u.email, u.phone_number, s.username AS seller_name, s.email AS seller_email,
               s.phone_number AS seller_phone, p.status, p.paid, p.purchase_date
        FROM purchases p
        JOIN books b ON p.book_id = b.id
        JOIN users u ON p.buyer_id = u.id
        JOIN users s ON p.seller_id = s.id
        WHERE p.id = %s
    """, (purchase_id,))
    
    purchase = cursor.fetchone()
    cursor.close()

    if not purchase:
        flash("Purchase request not found!", "danger")
        return redirect(url_for('admin_buy_requests'))

    return render_template('admin_buy_request_details.html', purchase=purchase)

@app.route('/admin/update_purchase/<int:purchase_id>', methods=['POST'])
def update_purchase(purchase_id):
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    new_status = request.form.get('status')
    new_paid_status = request.form.get('paid')  # Get paid status from form
    paid_value = 1 if new_paid_status == "True" else 0  # Convert to int

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE purchases SET status = %s, paid = %s WHERE id = %s", 
                   (new_status, paid_value, purchase_id))
    mysql.connection.commit()
    cursor.close()

    flash("Purchase details updated successfully!", "success")
    return redirect(url_for('admin_buy_requests'))  # Redirect to request list



if __name__ == '__main__':
    app.run(debug=True)
