import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename

# ========================================================
# 1. IMPORT LAYERS (Strict Flow: App -> Class)
# ========================================================
from classes.system_manager import SystemManager
from classes.customer import Customer
from classes.admin import Admin
from backend.car_handler import listAllCars

app = Flask(__name__)
app.secret_key = 'super_secret_key' 

# --- CONFIGURATION ---
UPLOAD_FOLDER = 'static/assets'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

system_manager = SystemManager()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =========================================
# ROUTES
# =========================================

@app.route('/')
def root(): return redirect(url_for('login'))

@app.route('/home')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET': session.clear()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # [OOP]: Customer Class acts as the Login Proxy
        current_user = Customer(username, password)
        result = current_user.login()

        if "successful" in result:
            try:
                parts = result.split('|')
                role = parts[2].split(':')[1].strip()
                
                session.clear()
                session['user_id'] = current_user.user_id 
                session['role'] = role
                session['username'] = username

                # [OOP]: Object fetches its own profile data
                user_data = current_user.get_profile_details()
                if user_data:
                    session['first_name'] = user_data['first_name']
                    session['last_name'] = user_data['last_name']
                    session['email'] = user_data['email_address']
                    session['phone_number'] = user_data['phone_number']
                
                flash("Welcome back!", "success")
                return redirect(url_for('admin_dashboard' if role == 'admin' else 'index'))
                    
            except (IndexError, ValueError):
                flash("Login error: Could not parse details.", "danger")
        else:
            flash(result, "danger")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET': session.clear()

    if request.method == 'POST':
        temp_customer = Customer(request.form['username'], request.form['password'])
        result = temp_customer.register(
            username=request.form['username'], password=request.form['password'],
            last=request.form['last_name'], first=request.form['first_name'],
            middle=request.form.get('middle_name', ''), gender=request.form['sex'],
            dob=request.form['dob'], email=request.form['email'], phone=request.form['phone']
        )
        
        if "successful" in result:
            flash("Account created! Please login.", "success")
            return redirect(url_for('login'))
        else:
            flash(result, "danger")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- CUSTOMER ROUTES ---

@app.route('/cars')
def customer_cars():
    if 'user_id' not in session: return redirect(url_for('login'))
    cars = system_manager.carList()
    return render_template('cars.html', cars=cars)

@app.route('/rent_car/<int:car_id>', methods=['GET', 'POST'])
def rent_car(car_id):
    if 'user_id' not in session: return redirect(url_for('login'))
        
    cars = system_manager.check_availability()
    car = next((c for c in cars if c.car_id == car_id), None)
    
    if not car:
        flash("Car unavailable.", "warning")
        return redirect(url_for('customer_cars'))
    
    if request.method == 'POST':
        current_user = Customer(session['username'], "")
        current_user.user_id = session['user_id']
        result = system_manager.rent_car_process(current_user, car_id, request.form['start_date'], request.form['end_date'])
        
        if "successful" in result: return render_template('success.html')
        else: flash(result, "danger")
            
    return render_template('rent_car.html', car=car)

@app.route('/rental_history')
def rental_history():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    current_user = Customer(session['username'], "")
    current_user.user_id = session['user_id']
    my_rentals = current_user.view_rental_history()
    visible_rentals = [r for r in my_rentals if r['status'] == 'Approved']
    
    return render_template('rental_history.html', rentals=visible_rentals)

# --- ADMIN ROUTES ---

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    
    # [OOP]: Admin Class now handles fetching all rentals
    admin = Admin(session['username'], "")
    all_rentals = admin.view_all_rentals()
    return render_template('admin_dashboard.html', rentals=all_rentals)

@app.route('/manage_cars')
def manage_cars():
    if 'user_id' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    admin = Admin(session['username'], "")
    return render_template('manage_cars.html', cars=admin.view_all_cars())

@app.route('/add_car', methods=['POST'])
def add_car():
    if 'role' not in session: return redirect(url_for('login'))
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f'assets/{filename}'

    admin = Admin(session['username'], "")
    admin.add_car(
        request.form['model'], 
        request.form['brand'], 
        request.form['price'], 
        image_path,
        request.form['capacity'],
        request.form['gasoline_type'],
        request.form['transmission']
        )
    flash("Car added successfully!", "success")
    return redirect(url_for('manage_cars'))

@app.route('/edit_car', methods=['POST'])
def edit_car_route():
    if 'role' not in session: return redirect(url_for('login'))
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f'assets/{filename}'

    admin = Admin(session['username'], "")
    result = admin.edit_car(
        request.form['car_id'], 
        request.form.get('brand'), 
        request.form.get('model'), 
        request.form.get('price'), 
        image_path,
        request.form.get('capacity'),
        request.form.get('gasoline_type'),
        request.form.get('transmission')
    )
    flash(result, "success" if "successfully" in result else "warning")
    return redirect(url_for('manage_cars'))

@app.route('/delete_car_form', methods=['POST'])
def delete_car_form():
    if 'role' not in session: return redirect(url_for('login'))
    admin = Admin(session['username'], "")
    admin.remove_car(request.form['car_id'])
    flash(f"Car ID {request.form['car_id']} deleted.", "warning")
    return redirect(url_for('manage_cars'))

@app.route('/view_rentals')
def view_rentals():
    if 'role' not in session: return redirect(url_for('login'))
    admin = Admin(session['username'], "")
    
    return render_template('view_rentals.html', rentals=admin.view_all_rentals())

@app.route('/verify_rentals')
def verify_rentals():
    if 'role' not in session: return redirect(url_for('login'))
    admin = Admin(session['username'], "")
    all_rentals = admin.view_all_rentals()
    pending = [r for r in all_rentals if r['status'] == 'Pending']
    return render_template('verify_rentals.html', rentals=pending)

@app.route('/update_rental_status/<int:rental_id>/<string:action>')
def update_rental_status(rental_id, action):
    if 'role' not in session: return redirect(url_for('login'))
    
    # [OOP]: Admin Object handles logic (DB calls are hidden inside)
    admin = Admin(session['username'], "")
    result = admin.process_rental(rental_id, action)
    
    flash(result, "success" if "Approved" in result else "warning")
    return redirect(url_for('verify_rentals'))

@app.route('/set_car_available/<int:car_id>')
def set_car_available(car_id):
    if 'role' not in session: return redirect(url_for('login'))
    
    # [OOP]: Admin Object sets availability
    admin = Admin(session['username'], "")
    admin.set_car_availability(car_id, 'available')
    
    flash(f"Car ID {car_id} is now AVAILABLE.", "success")
    return redirect(url_for('manage_cars'))

if __name__ == '__main__':
    app.run(debug=True, port=5500)