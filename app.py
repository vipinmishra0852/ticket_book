from flask import Flask, request, jsonify, render_template
from flask_mail import Mail, Message
from pymongo import MongoClient
import random
import re

app = Flask(__name__)

# Configuration for Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'vipinmishra0852@gmail.com'  # Use your Gmail address
app.config['MAIL_PASSWORD'] = 'bydz hyur sise mtyo'  # Use your App Password

mail = Mail(app)
otp_storage = {}

# MongoDB Atlas Connection
connection_string = 'mongodb+srv://vipinmishra0852:cqJCeLykkpGAQbz1@userdata.c4bg8.mongodb.net/?retryWrites=true&w=majority&appName=userData'  # Replace with your MongoDB connection string
try:
    client = MongoClient(connection_string, tls=True, tlsAllowInvalidCertificates=True)
    db = client['MuseumBookings']  # Use new database
    user_details_collection = db['userData']  # Use new collection
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

verified_email = None  # To store the verified email globally
selected_shows = {}  # To store the shows and tickets the user selects

@app.route('/')
def home():
    return render_template('home.html')


# Temporary storage for user details
user_data = {}


@app.route('/', methods=['POST'])
def handle_request():
    global verified_email, selected_shows, user_data
    req = request.get_json(silent=True, force=True)
    user_input = req['queryResult']['queryText']

    print(f"User input: {user_input}")  # Debugging statement

    # Check if the input contains email and needs OTP generation
    email = extract_email(user_input)
    if email and not verified_email:
        otp = generate_otp()
        otp_storage[email] = otp
        send_otp(email, otp)
        response = {
            "fulfillmentText": "OTP sent to your email. Please verify."
        }
    # Check if the input contains an OTP and validate it
    elif re.search(r'\b\d{6}\b', user_input):  # This checks if the input contains a 6-digit OTP
        otp = extract_otp(user_input)
        if otp and validate_otp(otp):
            response = {
                "fulfillmentText": "Congratulations, your email verification has been successfully done. Please provide your name, address, and contact number."
            }
        else:
            response = {
                "fulfillmentText": "Invalid OTP. Please try again."
            }
    # Handle user details and ticket booking
    else:
        if verified_email:
            # Handle ticket booking
            if "ticket" in user_input.lower():  # Check if the user is selecting tickets
                if not user_data.get('person_details'):
                    response = {
                        "fulfillmentText": "Please provide your name, address, and contact number before booking tickets."
                    }
                else:
                    # Extract selected shows
                    selected_shows = extract_show_selection(user_input)
                    print(f"Selected shows: {selected_shows}")  # Debugging statement

                    if selected_shows:
                        total_price = calculate_total_price(selected_shows)
                        try:
                            # Save booking details in user_data
                            user_data['booking_details'] = {
                                'selected_shows': selected_shows,
                                'total_price': total_price
                            }

                            # Send booking confirmation email
                            send_booking_confirmation(verified_email, selected_shows, total_price)

                            # Save all collected data in database
                            try:
                                # Print the document before the update
                                print("Document before update:",
                                      user_details_collection.find_one({'email': verified_email}))

                                # Update user_data with personal details and save to database
                                update_result = user_details_collection.update_one(
                                    {'email': verified_email},
                                    {'$set': {
                                        'person_details': user_data.get('person_details', {}),
                                        'contact_details': user_data.get('contact_details', {}),
                                        'booking_details': user_data['booking_details']
                                    }},
                                    upsert=True  # Ensure that the document is created if it doesn't exist
                                )

                                # Print the document after the update
                                print("Document after update:",
                                      user_details_collection.find_one({'email': verified_email}))

                                response = {
                                    "fulfillmentText": f"Booking confirmed! Your total is ₹{total_price}. Confirmation has been sent to your email."
                                }
                            except Exception as e:
                                response = {
                                    "fulfillmentText": "There was an error processing your booking. Please try again."
                                }
                                print(f"Error updating booking details in MongoDB: {e}")

                        except Exception as e:
                            response = {
                                "fulfillmentText": "There was an error processing your booking. Please try again."
                            }
                            print(f"Error sending booking confirmation email: {e}")

                    else:
                        response = {
                            "fulfillmentText": "Please specify valid shows and the number of tickets."
                        }
            else:
                # Collect user details if not yet collected
                if not user_data.get('person_details'):
                    user_details = extract_user_details(user_input)
                    print(f"Extracted user details: {user_details}")  # Debugging statement

                    if user_details:
                        user_data['person_details'] = user_details['person_details']
                        user_data['contact_details'] = user_details['contact_details']

                        # List of museum shows and prices
                        museum_shows = [
                            "Ancient Artifacts Exhibition – ₹500 / $6",
                            "The Evolution of Wildlife – ₹450 / $5.5",
                            "The Mysteries of Space – ₹600 / $7.5",
                            "Modern Sculptures Display – ₹400 / $5",
                            "Renaissance Masterpieces – ₹700 / $9",
                            "History of Indian Railways – ₹300 / $4",
                            "Cultural Heritage Showcase – ₹350 / $4.5",
                            "The World of Dinosaurs – ₹550 / $7",
                            "Futuristic Technologies – ₹650 / $8.5"
                        ]

                        # Constructing the response with the list of museum shows
                        shows_list = "\n".join(museum_shows)
                        response = {
                            "fulfillmentText": (
                                f"Your details have been saved temporarily.\n"
                                f"Please select the shows and the number of tickets for each show.\n"
                                f"Here are the available museum shows:\n{shows_list}\n"
                                "Would you like a description of any particular show?"
                            )
                        }

                    else:
                        response = {
                            "fulfillmentText": "It seems like your input was incomplete. Please provide your name, address, and contact number."
                        }

                else:
                    response = {
                        "fulfillmentText": "Please provide valid details including your name, address, and contact number."
                    }

        else:
            response = {
                "fulfillmentText": "Email is missing. Please provide your email first."
            }

    return jsonify(response)


# Function to extract show selection and ticket numbers
def extract_show_selection(text):
    # Define a comprehensive list of museum shows and their aliases
    show_names = {
        "Ancient Artifacts Exhibition": ["Artifacts Exhibition", "Ancient Artifacts", "Artifacts", "Ancient Exhibit"],
        "Evolution of Wildlife": ["Evolution of Wildlife", "Wildlife Evolution", "Wildlife Exhibit"],
        "Mysteries of Space": ["Mysteries of Space", "Space Mysteries", "Space Exhibit"],
        "Modern Sculptures Display": ["Modern Sculptures Display", "Sculptures Display", "Modern Sculptures"],
        "Renaissance Masterpieces": ["Renaissance Masterpieces", "Renaissance Art", "Masterpieces"],
        "History of Indian Railways": ["History of Indian Railways", "Indian Railways", "Railways History"],
        "Cultural Heritage Showcase": ["Cultural Heritage Showcase", "Heritage Showcase", "Cultural Showcase"],
        "World of Dinosaurs": ["World of Dinosaurs", "Dinosaurs World", "Dinosaur Exhibit"],
        "Futuristic Technologies": ["Futuristic Technologies", "Tech Innovations", "Future Tech"],
    }

    # Compile a flexible regex pattern to match ticket numbers and shows
    show_pattern = re.compile(r'(\d+)\s*(?:tickets?|seats?)\s*(?:for|of|to)?\s*(.+?)(?:\s+and\s+|,|\.|$)', re.IGNORECASE)
    shows = show_pattern.findall(text)
    selected_shows = {}

    # Normalize the shows extracted and map them to the official show names
    for quantity, show in shows:
        show = show.strip().lower()
        normalized_show = normalize_show_name(show)
        if normalized_show:
            selected_shows[normalized_show] = selected_shows.get(normalized_show, 0) + int(quantity)
        else:
            print(f"Unrecognized show name: {show}")

    return selected_shows



def normalize_show_name(show_name):
    show_names = {
        "Ancient Artifacts Exhibition": ["Artifacts Exhibition", "Ancient Artifacts", "Artifacts", "Ancient Exhibit"],
        "Evolution of Wildlife": ["Evolution of Wildlife", "Wildlife Evolution", "Wildlife Exhibit"],
        "Mysteries of Space": ["Mysteries of Space", "Space Mysteries", "Space Exhibit"],
        "Modern Sculptures Display": ["Modern Sculptures Display", "Sculptures Display", "Modern Sculptures"],
        "Renaissance Masterpieces": ["Renaissance Masterpieces", "Renaissance Art", "Masterpieces"],
        "History of Indian Railways": ["History of Indian Railways", "Indian Railways", "Railways History"],
        "Cultural Heritage Showcase": ["Cultural Heritage Showcase", "Heritage Showcase", "Cultural Showcase"],
        "World of Dinosaurs": ["World of Dinosaurs", "Dinosaurs World", "Dinosaur Exhibit"],
        "Futuristic Technologies": ["Futuristic Technologies", "Tech Innovations", "Future Tech"],
    }

    for official_name, aliases in show_names.items():
        for alias in aliases:
            if alias.lower() in show_name:
                return official_name
    return None



def calculate_total_price(selected_shows):
    prices = {
        "Ancient Artifacts Exhibition": 500,
        "Evolution of Wildlife": 450,
        "Mysteries of Space": 600,
        "Modern Sculptures Display": 400,
        "Renaissance Masterpieces": 700,
        "History of Indian Railways": 300,
        "Cultural Heritage Showcase": 350,
        "World of Dinosaurs": 550,
        "Futuristic Technologies": 650
    }

    total_price = 0
    for show, tickets in selected_shows.items():
        total_price += prices.get(show, 0) * tickets

    return total_price


# Utility functions
def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None


def extract_otp(text):
    match = re.search(r'\b\d{6}\b', text)
    return match.group(0) if match else None


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp(email, otp):
    msg = Message('Your OTP Code', sender='bklmemes69@gmail.com', recipients=[email])
    msg.body = f'Your OTP code is {otp}'
    mail.send(msg)


def validate_otp(otp):
    global verified_email
    for email, stored_otp in otp_storage.items():
        if otp == stored_otp:
            verified_email = email
            return True
    return False


def extract_user_details(text):
    # Adjusted patterns for name, address, and contact number
    name_pattern = r"(?:name is|My name is|I am)\s*(?P<name>[\w\s]+?)(?:,|\.|and|$)"
    address_pattern = r"(?:I live in|address is|live in|located at|My address is)\s*(?P<address>[\w\s,]+?)(?:,|\.|and|$)"
    contact_pattern = r"(?:my contact details are|contact number is|phone number is|mobile number is|my number is)\s*(?P<contact_number>\d{10})"

    # Try to match each part individually
    name_match = re.search(name_pattern, text, re.IGNORECASE)
    address_match = re.search(address_pattern, text, re.IGNORECASE)
    contact_match = re.search(contact_pattern, text, re.IGNORECASE)

    # Extract details if they are found
    name = name_match.group('name').strip() if name_match else None
    address = address_match.group('address').strip() if address_match else None
    contact_number = contact_match.group('contact_number').strip() if contact_match else None

    # Check if all details were found
    if name and address and contact_number:
        # Clean any unnecessary words from the name and address
        name = re.sub(r'\b(and|my)\b', '', name).strip()
        address = re.sub(r'\b(and|my|contact number is|phone number is|mobile number is)\b.*', '', address).strip()

        # Store the details in the required format
        user_details = {
            'person_details': {
                'name': name,
                'address': address
            },
            'contact_details': {
                'contact_number': contact_number
            }
        }
        return user_details
    else:
        return None



def send_booking_confirmation(email, shows, total_price):
    show_details = "\n".join([f"{show}: {tickets} ticket(s)" for show, tickets in shows.items()])
    message_body = f"Your booking has been confirmed!\n\nShows:\n{show_details}\n\nTotal Price: ₹{total_price}"

    msg = Message('Booking Confirmation', sender='vipinmishra0852@gmail.com', recipients=[email])
    msg.body = message_body
    mail.send(msg)


if __name__ == '__main__':
    app.run(debug=True)
