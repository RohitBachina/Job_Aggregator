# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests

# Import LangChain components
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --- APP AND DATABASE CONFIGURATION ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-fallback-secret-key-for-development')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- API AND MODEL CONFIGURATION ---
ADZUNA_APP_ID = os.environ.get("631767ae")
ADZUNA_APP_KEY = os.environ.get("a277831d59f1cb89f7a7fe9cf20d62c5")
GOOGLE_API_KEY = os.environ.get("AIzaSyC07k2BYqL5-VE4XkRU9NvMq2uIORfAq7c")

# --- LANGCHAIN SETUP ---
llm_chain = None
if GOOGLE_API_KEY:
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GOOGLE_API_KEY)
        prompt_template = """
        You are an expert at parsing user job searches. Extract the core job title/keywords and the location from a user's query.
        Return the result as a simple, two-line string: job keywords on the first line, location on the second.
        If no location is mentioned, return "any" for the location.
        User Query: {query}
        Your Output:
        """
        PROMPT = PromptTemplate.from_template(prompt_template)
        llm_chain = PROMPT | llm | StrOutputParser()
    except Exception as e:
        print(f"Warning: Could not initialize LangChain. AI features will be disabled. Error: {e}")
        llm_chain = None

# --- DATABASE MODEL ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- AUTH ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user); return redirect(url_for('home'))
        else: flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        if User.query.filter_by(username=request.form.get('username')).first():
            flash('Username already exists.', 'error')
        else:
            new_user = User(username=request.form.get('username')); new_user.set_password(request.form.get('password'))
            db.session.add(new_user); db.session.commit()
            flash('Account created! Please log in.', 'success'); return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

# --- MAIN APP ROUTES ---
@app.route('/')
@login_required
def home():
    return render_template('index.html')

def call_adzuna_api(job_role, location, user_query):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return render_template('results.html', error="The job search service is not configured correctly.")
    
    country_code = 'gb'
    api_url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
    params = {'app_id': ADZUNA_APP_ID, 'app_key': ADZUNA_APP_KEY, 'results_per_page': 20, 'what': job_role, 'where': location}
    response = requests.get(api_url, params=params)
    response.raise_for_status()
    data = response.json()
    jobs = data.get('results', [])
    return render_template('results.html', jobs=jobs, query=user_query, location=location)

@app.route('/search', methods=['POST'])
@login_required
def search():
    job_role = request.form.get('search_query', '')
    location = request.form.get('location', '')
    user_query = f"{job_role} in {location}" if location else job_role
    return call_adzuna_api(job_role, location, user_query)

@app.route('/ai-search', methods=['POST'])
@login_required
def ai_search():
    if not llm_chain:
        return render_template('results.html', error="AI Assistant is unavailable. Please check the Google AI API key.")
    
    user_query = request.form.get('descriptive_query')
    try:
        llm_response = llm_chain.invoke({"query": user_query})
        lines = llm_response.strip().split('\n')
        job_role = lines[0].strip()
        location = lines[1].strip() if len(lines) > 1 else 'any'
        if location.lower() == 'any': location = ''
        return call_adzuna_api(job_role, location, user_query)
    except Exception as e:
        print(f"An error occurred during AI search: {e}")
        return render_template('results.html', error="Could not process your search via AI.")

# Initialize the database
with app.app_context():
    db.create_all()

# The following is for local development only
if __name__ == '__main__':
    app.run(debug=True)
