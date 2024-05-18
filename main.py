from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from supabase import create_client, Client
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import secrets
import jwt

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow all origins (not recommended for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


import os
load_dotenv()
#app = FastAPI()

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# OAuth2 scheme for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWT secret and algorithm

def generate_secret():
    return secrets.token_hex(16)

SECRET_KEY = generate_secret()
ALGORITHM = "HS256"

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

# Models
class Ticket(BaseModel):
    ticket_id: int
    seat_number: Optional[str] = None
    flight_number: str
    payment_id: int
    passenger_id: Optional[str] = None
    date_of_booking: Optional[date] = None
    status: str

class Flight(BaseModel):
    flight_number: str
    departure_city: str
    destination_city: str
    date: date
    time: str

class Payment(BaseModel):
    payment_id: int
    amount: float
    date: date
    method: str

class User(BaseModel):
    ssn: str
    username: str
    email: str
    role: str = None

class Token(BaseModel):
    access_token: str
    token_type: str

class AdminChanges(BaseModel):
    admin_ssn: str
    changes_count: int

class Maintenance(BaseModel):
    maintenance_id: Optional[int] = None
    plane_id: str
    employee_id: str
    maintenance_type: str
    maintenance_date: date




def send_email(to_email: str, subject: str, content: str):
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=content)
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

    except Exception as e:
        print(e.message)

        
# In-memory token blacklist
token_blacklist = []

# Utility function to add a token to the blacklist
def blacklist_token(token: str):
    token_blacklist.append(token)

# Function to check if a token is blacklisted
def is_token_blacklisted(token: str) -> bool:
    return token in token_blacklist

# Override the get_current_user function to check the blacklist
def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token has been invalidated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        ssn = payload.get("sub")
        if ssn is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_data = supabase.table("person").select("*").eq("ssn", ssn).execute()
    if not user_data.data:
        raise HTTPException(status_code=401, detail="User not found")

    user_info = user_data.data[0]
    return User(ssn=user_info["ssn"], username=user_info["username"], email=user_info["email"])

def get_user_roles(user: User):
    roles = []
    if supabase.table("admin").select("ssn").eq("ssn", user.ssn).execute().data:
        roles.append("Admin")
    if supabase.table("employee").select("ssn").eq("ssn", user.ssn).execute().data:
        roles.append("Employee")
    if supabase.table("passenger").select("ssn").eq("ssn", user.ssn).execute().data:
        roles.append("Passenger")
    return roles

def require_roles(required_roles: List[str]):
    def role_checker(user: User = Depends(get_current_user)):
        user_roles = get_user_roles(user)
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return role_checker

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Passenger functions
@app.post("/passenger/ticket", response_model=Ticket)
async def add_ticket(ticket: Ticket, user: User = Depends(require_roles(["Passenger"]))):
    if ticket.passenger_id != user.ssn:
        raise HTTPException(status_code=403, detail="You do not have permission to add a ticket for another passenger")
    ticket_data = ticket.model_dump(exclude={"ticket_id"})
    response = supabase.table("ticket").insert(ticket_data).execute()
    if response.status_code != 201:
        raise HTTPException(status_code=400, detail="Error adding ticket")
    send_email(user.email, "Ticket Booked", f"Your ticket for flight {ticket.flight_number} has been booked successfully, waiting for confirmation")
    return response.data[0]

@app.delete("/passenger/ticket/{ticket_id}")
async def remove_ticket(ticket_id: int, user: User = Depends(require_roles(["Passenger"]))):
    # Ensure the ticket belongs to the current user via the ticket table
    ticket_data = supabase.table("ticket").select("*").eq("ticket_id", ticket_id).eq("passenger_id", user.ssn).execute()
    if not ticket_data.data:
        raise HTTPException(status_code=403, detail="You do not have permission to remove this ticket")

    response = supabase.table("ticket").update({"status": "removed"}).eq("ticket_id", ticket_id).execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error removing ticket")
    
    flight_number = ticket_data.data[0]["flight_number"]
    send_email(user.email, "Ticket Cancelled", f"Your ticket for flight {flight_number} has been cancelled")
    return {"message": "Ticket removed"}

@app.put("/passenger/ticket/{ticket_id}", response_model=Ticket)
async def edit_ticket(ticket_id: int, ticket: Ticket, user: User = Depends(require_roles(["Passenger"]))):
    # Ensure the ticket belongs to the current user via the ticket table
    ticket_data = supabase.table("ticket").select("*").eq("ticket_id", ticket_id).eq("passenger_id", user.ssn).execute()
    if not ticket_data.data:
        raise HTTPException(status_code=403, detail="You do not have permission to edit this ticket")

    response = supabase.table("ticket").update(ticket.model_dump()).eq("ticket_id", ticket_id).execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error editing ticket")

    send_email(user.email, "Ticket Updated", f"Your ticket for flight {ticket.flight_number} has been updated")
    return response.data[0]


@app.get("/passenger/flights", response_model=List[Flight])
async def search_flights(departure_city: str, destination_city: str, travel_date: date):
    if travel_date < date.today():
        raise HTTPException(status_code=400, detail="Travel date cannot be in the past")
    if departure_city == destination_city:
        raise HTTPException(status_code=400, detail="Departure and destination cities cannot be the same")
    if not departure_city or not destination_city:
        raise HTTPException(status_code=400, detail="Departure and destination cities are required")
    if not travel_date:
        raise HTTPException(status_code=400, detail="Travel date is required")
    response = supabase.table("flight").select("*").eq("departure_city", departure_city).eq("destination_city", destination_city).eq("date", travel_date).execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error searching flights")
    return response.data

@app.post("/passenger/book_seat", response_model=Ticket)
async def book_seat(ticket: Ticket, user: User = Depends(require_roles(["Passenger"]))):
    # Check if the seat is already booked
    existing_ticket_response = supabase.table("ticket").select("*").eq("seat_number", ticket.seat_number).eq("flight_number", ticket.flight_number).eq("status", "active").execute()
    if existing_ticket_response.data:
        raise HTTPException(status_code=400, detail="Seat already booked")

    # Check if the passenger has already booked 10 seats for this flight
    passenger_tickets_response = supabase.table("ticket").select("*").eq("passenger_id", ticket.passenger_id).eq("flight_number", ticket.flight_number).execute()
    if len(passenger_tickets_response.data) >= 10:
        raise HTTPException(status_code=400, detail="Passenger cannot book more than 10 seats on a flight")

    response = supabase.table("ticket").insert(ticket.model_dump()).execute()
    if response.status_code != 201:
        raise HTTPException(status_code=400, detail="Error booking seat")
    
    send_email(user.email, "Seat Booked", f"Your seat {ticket.seat_number} for flight {ticket.flight_number} has been booked successfully")
    return response.data[0]

@app.post("/passenger/payment", response_model=Payment)
async def do_payment(payment: Payment, user: User = Depends(require_roles(["Passenger"]))):
    payment_data = payment.model_dump(exclude={"payment_id"})
    response = supabase.table("payment").insert(payment_data).execute()
    if response.status_code != 201:
        raise HTTPException(status_code=400, detail="Error processing payment")
    return response.data[0]

# Admin functions
@app.post("/admin/ticket", response_model=Ticket)
async def add_ticket_admin(ticket: Ticket, user: User = Depends(require_roles(["Admin"]))):
    ticket_data = ticket.model_dump(exclude={"ticket_id"})
    response = supabase.table("ticket").insert(ticket_data).execute()
    if response.status_code != 201:
        raise HTTPException(status_code=400, detail="Error adding ticket")
    send_email(user.email, "Ticket Booked", f"Ticket for flight {ticket.flight_number} has been booked successfully")
    return response.data[0]

@app.delete("/admin/ticket/{ticket_id}")
async def remove_ticket_admin(ticket_id: int, user: User = Depends(require_roles(["Admin"]))):

    response = supabase.table("ticket").update({"status": "removed"}).eq("ticket_id", ticket_id).execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error removing ticket")
    send_email(user.email, "Ticket Cancelled", f"Ticket for flight {ticket_id} has been cancelled")

    return {"message": "Ticket removed"}

@app.put("/admin/ticket/{ticket_id}", response_model=Ticket)
async def edit_ticket_admin(ticket_id: int, ticket: Ticket, user: User = Depends(require_roles(["Admin"]))):
    response = supabase.table("ticket").update(ticket.model_dump()).eq("ticket_id", ticket_id).execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error editing ticket")
    send_email(user.email, "Ticket Updated", f"Ticket for flight {ticket.flight_number} has been updated")
    return response.data[0]

@app.put("/admin/promote_waitlisted/{ticket_id}")
async def promote_waitlisted(ticket_id: str, user: User = Depends(require_roles(["Admin"]))):
    # Update the status of the ticket to active
    response = supabase.table("ticket").update({"status": "active"}).eq("ticket_id", ticket_id).execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error promoting passenger")
    
    # Get the passenger's email
    passenger_data = supabase.table("passenger").select("*").eq("ssn", response.data[0]["passenger_id"]).execute()
    if not passenger_data.data:
        raise HTTPException(status_code=400, detail="Error fetching passenger data")
    send_email(passenger_data.data[0]["email"], "Ticket Confirmed", f"Your ticket for flight {response.data[0]['flight_number']} has been confirmed")
    return {"message": "Passenger promoted"}

@app.get("/admin/reports/active_flights", response_model=List[Flight])
async def active_flights(user: User = Depends(require_roles(["Admin"]))):
    response = supabase.table("flight").select("*").eq("date", date.today()).execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error fetching active flights")
    return response.data

@app.get("/admin/reports/booking_percentage")
async def booking_percentage(flight_date: date, user: User = Depends(require_roles(["Admin"]))):
    query = """
    SELECT
        f.flight_number,
        COALESCE(SUM(ast.number_of_seats), 0) AS total_seats,
        COUNT(t.ticket_id) AS booked_seats,
        CASE
            WHEN COALESCE(SUM(ast.number_of_seats), 0) = 0 THEN 0
            ELSE (COUNT(t.ticket_id)::float / COALESCE(SUM(ast.number_of_seats), 0)) * 100
        END AS booking_percentage
    FROM
        flight f
        JOIN plane p ON f.plane_id = p.registration_number
        JOIN aircraft_seatstype ast ON p.aircraft_id = ast.aircraft_id
        LEFT JOIN ticket t ON f.flight_number = t.flight_number AND t.status = 'active'
    WHERE
        f.date = :flight_date
    GROUP BY
        f.flight_number;
    """
    
    response = supabase.rpc("query", {"query": query, "flight_date": flight_date}).execute()
    
    if response.status_code != 200 or not response.data:
        raise HTTPException(status_code=400, detail="Error fetching booking percentages")
    
    return response.data

@app.get("/admin/reports/payments", response_model=List[Payment])
async def confirmed_payments(user: User = Depends(require_roles(["Admin"]))):
    query = """
    SELECT
        p.payment_id,
        p.amount,
        p.date,
        p.method
    FROM
        payment p
        JOIN ticket t ON p.payment_id = t.payment_id
    WHERE
        t.status = 'confirmed';
    """
    
    response = supabase.rpc("query", {"query": query}).execute()
    
    if response.status_code != 200 or not response.data:
        raise HTTPException(status_code=400, detail="Error fetching confirmed payments")
    
    return response.data

@app.get("/admin/reports/waitlisted_passengers")
async def waitlisted_passengers(flight_number: str, user: User = Depends(require_roles(["Admin"]))):
    # Query the database to get waitlisted passengers for the specified flight
    query = """
    SELECT person.ssn, person.first_name, person.father_name, person.family, person.email, person.phone
    FROM ticket
    JOIN passenger ON ticket.passenger_id = passenger.ssn
    JOIN person ON passenger.ssn = person.ssn
    WHERE ticket.flight_number = :flight_number AND ticket.status = 'waitlisted';
    """
    
    response = supabase.rpc("query", {"query": query, "flight_number": flight_number}).execute()
    
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error fetching waitlisted passengers")
    
    return response.data

@app.get("/admin/reports/load_factor")
async def average_load_factor(flight_date: date, user: User = Depends(require_roles(["Admin"]))):
    query = """
    SELECT
        p.registration_number,
        COALESCE(seat_counts.total_seats, 0) AS total_seats,
        COALESCE(booked_counts.booked_seats, 0) AS booked_seats,
        CASE
            WHEN COALESCE(seat_counts.total_seats, 0) = 0 THEN 0
            ELSE (COALESCE(booked_counts.booked_seats, 0)::float / COALESCE(seat_counts.total_seats, 0)) * 100
        END AS load_factor
    FROM
        plane p
        LEFT JOIN (
            SELECT
                p.registration_number,
                SUM(ast.number_of_seats) AS total_seats
            FROM
                plane p
                JOIN aircraft_seatstype ast ON p.aircraft_id = ast.aircraft_id
            GROUP BY
                p.registration_number
        ) AS seat_counts ON p.registration_number = seat_counts.registration_number
        LEFT JOIN (
            SELECT
                f.plane_id AS registration_number,
                COUNT(t.ticket_id) AS booked_seats
            FROM
                flight f
                LEFT JOIN ticket t ON f.flight_number = t.flight_number AND t.status = 'active'
            WHERE
                f.date = :flight_date
            GROUP BY
                f.plane_id
        ) AS booked_counts ON p.registration_number = booked_counts.registration_number;
    """
    
    response = supabase.rpc("query", {"query": query, "flight_date": flight_date}).execute()
    
    if response.status_code != 200 or not response.data:
        raise HTTPException(status_code=400, detail="Error fetching load factors")
    
    return response.data




@app.get("/admin/reports/ticket_cancelled")
async def cancelled_tickets(user: User = Depends(require_roles(["Admin"]))):
    query = """
    SELECT
        t.ticket_id,
        t.seat_number,
        t.flight_number,
        t.payment_id,
        t.passenger_id,
        p.first_name,
        p.father_name,
        p.family,
        p.email,
        p.phone
    FROM

        ticket t
        JOIN passenger p ON t.passenger_id = p.ssn
    WHERE
        t.status = 'cancelled';
    """
    response = supabase.rpc("query", {"query": query}).execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error fetching cancelled tickets")

    return response.data


@app.get("/admin/reports/changes_by_admin", response_model=List[AdminChanges])
async def changes_by_admin(user: User = Depends(require_roles(["Admin"]))):
    query = """
    SELECT
        m.ssn AS admin_ssn,
        COUNT(*) AS changes_count
    FROM
        manage m
    GROUP BY
        m.ssn;
    """

    response = supabase.rpc("query", {"query": query}).execute()
    
    if response.status_code != 200 or not response.data:
        raise HTTPException(status_code=400, detail="Error fetching changes by admin")
    
    return response.data

@app.post("/maintenance", response_model=Maintenance)
async def create_maintenance(maintenance: Maintenance, user: User = Depends(require_roles(["Employee", "Admin"]))):
    maintenance_data = maintenance.model_dump()
    response = supabase.table("maintenance").insert(maintenance_data).execute()
    if response.status_code != 201:
        raise HTTPException(status_code=400, detail="Error creating maintenance record")
    return response.data[0]

@app.get("/maintenance", response_model=List[Maintenance])
async def get_maintenance(plane_id: Optional[str] = None, employee_id: Optional[str] = None, user: User = Depends(require_roles(["Employee", "Admin"]))):
    query = supabase.table("maintenance").select("*")
    if plane_id:
        query = query.eq("plane_id", plane_id)
    if employee_id:
        query = query.eq("employee_id", employee_id)
    response = query.execute()
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error fetching maintenance records")
    return response.data


@app.get("/maintenance/last", response_model=List[Maintenance])
async def get_last_maintenance(user: User = Depends(require_roles(["Employee", "Admin"]))):
    query = """
    -- Query to fetch the last maintenance in the past
    SELECT
        m1.plane_id,
        m1.maintenance_id,
        m1.employee_id,
        m1.maintenance_type,
        m1.maintenance_date,
        m1.notes
    FROM
        maintenance m1
        JOIN (
            SELECT
                plane_id,
                MAX(maintenance_date) AS max_date
            FROM
                maintenance
            WHERE
                maintenance_date <= CURRENT_DATE
            GROUP BY
                plane_id
        ) m2 ON m1.plane_id = m2.plane_id AND m1.maintenance_date = m2.max_date
    """
    
    response = supabase.rpc("query", {"query": query}).execute()
    
    if response.status_code != 200 or not response.data:
        raise HTTPException(status_code=400, detail="Error fetching maintenance records")
    
    return response.data


@app.get("/maintenance/next", response_model=List[Maintenance])
async def get_next_maintenance(user: User = Depends(require_roles(["Employee", "Admin"]))):
    query = """
    SELECT
        m.plane_id,
        m.maintenance_id,
        m.employee_id,
        m.maintenance_type,
        m.maintenance_date,
        m.notes
    FROM
        maintenance m
    WHERE
        m.maintenance_date > CURRENT_DATE;
    """
    
    response = supabase.rpc("query", {"query": query}).execute()
    
    if response.status_code != 200 or not response.data:
        raise HTTPException(status_code=400, detail="Error fetching next maintenance records")
    
    return response.data

# General functions
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Add your logic to authenticate the user and return a token
    auth_response = supabase.auth.sign_in_with_password({
        "email": form_data.username,
        "password": form_data.password
    })
    if auth_response["user"] is not None:
        return {"access_token": auth_response["access_token"], "token_type": "bearer"}
    else:
        raise HTTPException(status_code=400, detail="Invalid credentials")

# Endpoint to handle logout
@app.post("/logout")
async def logout(user: User = Depends(get_current_user), token: str = Depends(oauth2_scheme)):
    blacklist_token(token)
    return {"message": "Logged out successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app=app)