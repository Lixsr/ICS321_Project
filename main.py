from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from supabase import create_client, Client
from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import date
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import secrets
import jwt

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


import os
load_dotenv()
app = FastAPI()

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# OAuth2 scheme for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWT secret and algorithm

def generate_secret():
    return secrets.token_hex(16)

SECRET_KEY = "generate_secret()"
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
    date_of_booking: Optional[str] = None
    status: str

class Flight(BaseModel):
    flight_number: str
    departure_city: str
    destination_city: str
    date: str
    time: str

class Payment(BaseModel):
    payment_id: int
    amount: float
    date: str
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
    maintenance_date: str




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


def find_available_seat(flight_number: str):
    query = """
    SELECT s.seat_number
    FROM seat s
    LEFT JOIN ticket t ON s.seat_number = t.seat_number AND s.flight_id = t.flight_number AND t.status NOT IN ('active', 'waitlist')
    WHERE s.flight_id = :flight_number AND t.seat_number IS NULL
    LIMIT 1;
    """

    try:
        response = supabase.rpc("query", {"query": query, "flight_number": flight_number}).execute()
        return response.data[0]["seat_number"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)



# Passenger functions
@app.post("/passenger/ticket", response_model=Ticket)
async def add_ticket(ticket: Ticket, user: User = Depends(require_roles(["Passenger"]))):
    if ticket.passenger_id != user.ssn:
        raise HTTPException(status_code=403, detail="You do not have permission to add a ticket for another passenger")
    ticket_data = ticket.model_dump(exclude={"ticket_id"})
    try:
        response = supabase.table("ticket").insert(ticket_data).execute()
        send_email(user.email, "Ticket Booked", f"Ticket for flight {ticket.flight_number} has been booked successfully")
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)
    return response.data[0]

@app.delete("/passenger/ticket/{ticket_id}")
async def remove_ticket(ticket_id: int, user: User = Depends(require_roles(["Passenger"]))):
    # Ensure the ticket belongs to the current user via the ticket table
    ticket_data = supabase.table("ticket").select("*").eq("ticket_id", ticket_id).eq("passenger_id", user.ssn).execute()
    if not ticket_data.data:
        raise HTTPException(status_code=403, detail="You do not have permission to remove this ticket")


    try:
        response = supabase.table("ticket").update({"status": "removed"}).eq("ticket_id", ticket_id).execute()
        flight_number = ticket_data.data[0]["flight_number"]
        send_email(user.email, "Ticket Cancelled", f"Your ticket for flight {flight_number} has been cancelled")
        return {"message": "Ticket removed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)
    

@app.put("/passenger/ticket/{ticket_id}", response_model=Ticket)
async def edit_ticket(ticket_id: int, ticket: Ticket, user: User = Depends(require_roles(["Passenger"]))):
    # Ensure the ticket belongs to the current user via the ticket table
    ticket_data = supabase.table("ticket").select("*").eq("ticket_id", ticket_id).eq("passenger_id", user.ssn).execute()
    if not ticket_data.data:
        raise HTTPException(status_code=403, detail="You do not have permission to edit this ticket")


    try:
        response = supabase.table("ticket").update(ticket.model_dump()).eq("ticket_id", ticket_id).execute()
        send_email(user.email, "Ticket Updated", f"Your ticket for flight {ticket.flight_number} has been updated")
    except:
        raise HTTPException(status_code=400, detail=e.message)

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
    try:
        response = supabase.table("flight").select("*").eq("departure_city", departure_city).eq("destination_city", destination_city).eq("date", travel_date).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)

    return response.data

@app.post("/passenger/book_seat", response_model=Ticket)
async def book_seat(ticket: Ticket, user: User = Depends(require_roles(["Passenger"]))):

    try:

        response = supabase.table("ticket").insert(ticket.model_dump()).execute()
    
        send_email(user.email, "Seat Booked", f"Your seat {ticket.seat_number} for flight {ticket.flight_number} has been booked successfully")

    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)
    return response.data[0]

@app.post("/passenger/payment", response_model=Payment)
async def do_payment(payment: Payment, user: User = Depends(require_roles(["Passenger"]))):
    payment_data = payment.model_dump(exclude={"payment_id"})
    try:
        response = supabase.table("payment").insert(payment_data).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)
    return response.data[0]

# Admin functions
@app.post("/admin/ticket", response_model=Ticket)
async def add_ticket_admin(ticket: Ticket, user: User = Depends(require_roles(["Admin"]))):
    ticket_data = ticket.model_dump(exclude={"ticket_id"})
    try:
        response = supabase.table("ticket").insert(ticket_data).execute()
        send_email(user.email, "Ticket Booked", f"Ticket for flight {ticket.flight_number} has been booked successfully")
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)
    return response.data[0]

@app.delete("/admin/ticket/{ticket_id}")
async def remove_ticket_admin(ticket_id: int, user: User = Depends(require_roles(["Admin"]))):
    
    try:
        response = supabase.table("ticket").update({"status": "removed"}).eq("ticket_id", ticket_id).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)

    send_email(user.email, "Ticket Cancelled", f"Ticket for flight {ticket_id} has been cancelled")

    return {"message": "Ticket removed"}

@app.put("/admin/ticket/{ticket_id}", response_model=Ticket)
async def edit_ticket_admin(ticket_id: int, ticket: Ticket, user: User = Depends(require_roles(["Admin"]))):
    try:
        response = supabase.table("ticket").update(ticket.model_dump()).eq("ticket_id", ticket_id).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)
    send_email(user.email, "Ticket Updated", f"Ticket for flight {ticket.flight_number} has been updated")
    return response.data[0]

@app.put("/admin/promote_waitlisted/{ticket_id}")
async def promote_waitlisted(ticket_id: str, user: User = Depends(require_roles(["Admin"]))):
    # Update the status of the ticket to active
    try:
        response = supabase.table("ticket").update({"status": "active"}).eq("ticket_id", ticket_id).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)
    
    # Get the passenger's email
    try:
        passenger_data = supabase.table("passenger").select("*").eq("ssn", response.data[0]["passenger_id"]).execute()
    except Exception as e:

        raise HTTPException(status_code=400, detail=e.message)
    send_email(passenger_data.data[0]["email"], "Ticket Confirmed", f"Your ticket for flight {response.data[0]['flight_number']} has been confirmed")
    return {"message": "Passenger promoted"}

@app.get("/admin/reports/active_flights", response_model=List[Flight])
async def active_flights(user: User = Depends(require_roles(["Admin"]))):
    try:
        response = supabase.table("flight").select("*").eq("date", date.today()).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)
    return response.data


@app.get("/admin/reports/booking_percentage")
async def booking_percentage(flight_date: date, user: User = Depends(require_roles(["Admin"]))):
    try:
        # Fetch flights on the given date
        flights_response = supabase.table("flight").select("flight_number, plane_id").eq("date", flight_date).execute()

        flights_data = flights_response.data
        booking_percentages = []

        for flight in flights_data:
            flight_number = flight["flight_number"]
            plane_id = flight["plane_id"]

            # Fetch total seats for the plane
            plane_response = supabase.table("plane").select("aircraft_id").eq("registration_number", plane_id).single().execute()
        
            aircraft_id = plane_response.data["aircraft_id"]
            seats_response = supabase.table("aircraft_seatstype").select("number_of_seats").eq("aircraft_id", aircraft_id).execute()

            total_seats = sum(seat["number_of_seats"] for seat in seats_response.data)

            # Fetch booked seats for the flight
            tickets_response = supabase.table("ticket").select("ticket_id").eq("flight_number", flight_number).eq("status", "active").execute()
            booked_seats = len(tickets_response.data)

            # Calculate booking percentage
            booking_percentage = (booked_seats / total_seats) * 100 if total_seats > 0 else 0
            booking_percentages.append({
                "flight_number": flight_number,
                "total_seats": total_seats,
                "booked_seats": booked_seats,
                "booking_percentage": booking_percentage
            })

        return booking_percentages
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)

@app.get("/admin/reports/payments", response_model=List[dict[str, Any]])
async def confirmed_payments(user: User = Depends(require_roles(["Admin"]))):
    try:
        # Fetch confirmed tickets
        tickets_response = supabase.table("ticket").select("payment_id").eq("status", "confirmed").execute()

        payment_ids = [ticket["payment_id"] for ticket in tickets_response.data]
        
        if not payment_ids:
            return []
        
        # Fetch payments related to the confirmed tickets
        payments_response = supabase.table("payment").select("*").in_("payment_id", payment_ids).execute()


        return payments_response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)


@app.get("/admin/reports/waitlisted_passengers")
async def waitlisted_passengers(flight_number: str, user: User = Depends(require_roles(["Admin"]))):
    try:
        # Fetch waitlisted tickets for the specified flight
        tickets_response = supabase.table("ticket").select("passenger_id").eq("flight_number", flight_number).eq("status", "waitlisted").execute()
   
        passenger_ids = [ticket["passenger_id"] for ticket in tickets_response.data]
        
        if not passenger_ids:
            return []
        
        # Fetch passengers related to the waitlisted tickets
        passengers_response = supabase.table("passenger").select("ssn").in_("ssn", passenger_ids).execute()

        passenger_ssns = [passenger["ssn"] for passenger in passengers_response.data]
        
        # Fetch person details related to the passengers
        persons_response = supabase.table("person").select("ssn, first_name, father_name, family, email, phone").in_("ssn", passenger_ssns).execute()

        return persons_response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)

@app.get("/admin/reports/load_factor")
async def average_load_factor(flight_date: date, user: User = Depends(require_roles(["Admin"]))):
    try:
        # Fetch total seats for each plane
        planes_response = supabase.table("plane").select("registration_number, aircraft_id").execute()

        seat_counts = {}
        planes_data = planes_response.data
        for plane in planes_data:
            plane_id = plane["registration_number"]
            aircraft_id = plane["aircraft_id"]
            seats_response = supabase.table("aircraft_seatstype").select("number_of_seats").eq("aircraft_id", aircraft_id).execute()
            if seats_response.data:
                seat_counts[plane_id] = sum(seat["number_of_seats"] for seat in seats_response.data)
            else:
                seat_counts[plane_id] = 0

        # Fetch booked seats for each plane on the given date
        flights_response = supabase.table("flight").select("plane_id, flight_number").eq("date", flight_date).execute()

        booked_counts = {}
        flights_data = flights_response.data
        for flight in flights_data:
            plane_id = flight["plane_id"]
            flight_number = flight["flight_number"]
            tickets_response = supabase.table("ticket").select("ticket_id").eq("flight_number", flight_number).eq("status", "active").execute()
            if tickets_response.data:
                booked_counts[plane_id] = len(tickets_response.data)
            else:
                booked_counts[plane_id] = 0

        # Combine results and calculate load factor
        load_factors = []
        for plane_id in seat_counts:
            total_seats = seat_counts[plane_id]
            booked_seats = booked_counts.get(plane_id, 0)
            load_factor = (booked_seats / total_seats) * 100 if total_seats > 0 else 0
            load_factors.append({
                "registration_number": plane_id,
                "total_seats": total_seats,
                "booked_seats": booked_seats,
                "load_factor": load_factor
            })

        return load_factors
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)


@app.get("/admin/reports/ticket_cancelled")
async def cancelled_tickets(user: User = Depends(require_roles(["Admin"]))):
    try:
        # Fetch cancelled tickets
        tickets_response = supabase.table("ticket").select("ticket_id, seat_number, flight_number, payment_id, passenger_id").eq("status", "cancelled").execute()
        if tickets_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Error fetching cancelled tickets")
        
        cancelled_tickets = tickets_response.data
        
        if not cancelled_tickets:
            return []
        
        passenger_ids = [ticket["passenger_id"] for ticket in cancelled_tickets]
        
        # Fetch passengers related to the cancelled tickets
        passengers_response = supabase.table("passenger").select("ssn").in_("ssn", passenger_ids).execute()
        if passengers_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Error fetching passengers")
        
        passenger_ssns = [passenger["ssn"] for passenger in passengers_response.data]
        
        # Fetch person details related to the passengers
        persons_response = supabase.table("person").select("ssn, first_name, father_name, family, email, phone").in_("ssn", passenger_ssns).execute()
        if persons_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Error fetching persons")
        
        persons = {person["ssn"]: person for person in persons_response.data}
        
        # Combine ticket and person details
        for ticket in cancelled_tickets:
            passenger_id = ticket["passenger_id"]
            if passenger_id in persons:
                ticket.update(persons[passenger_id])
        
        return cancelled_tickets
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@app.get("/admin/reports/changes_by_admin", response_model=List[AdminChanges])
async def changes_by_admin(user: User = Depends(require_roles(["Admin"]))):
    try:
        # Fetch changes by admin
        changes_response = supabase.table("manage").select("ssn, count(*) as changes_count").group("ssn").execute()
        if not changes_response.data:
            raise HTTPException(status_code=400, detail="Error fetching changes by admin")
        
        return changes_response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/maintenance", response_model=Maintenance)
async def create_maintenance(maintenance: Maintenance, user: User = Depends(require_roles(["Employee", "Admin"]))):
    maintenance_data = maintenance.model_dump()
    try:
        response = supabase.table("maintenance").insert(maintenance_data).execute()
    except Exception as e:
         raise HTTPException(status_code=400, detail=e.message)
    return response.data[0]

@app.get("/maintenance", response_model=List[Maintenance])
async def get_maintenance(plane_id: Optional[str] = None, employee_id: Optional[str] = None, user: User = Depends(require_roles(["Employee", "Admin"]))):
    query = supabase.table("maintenance").select("*")
    if plane_id:
        query = query.eq("plane_id", plane_id)
    if employee_id:
        query = query.eq("employee_id", employee_id)
    try:
        response = query.execute()
    except Exception as e:
         raise HTTPException(status_code=400, detail=e.message)
    return response.data

@app.get("/maintenance/last", response_model=List[Maintenance])
async def get_last_maintenance(user: User = Depends(require_roles(["Employee", "Admin"]))):
    try:
        # Fetch the last maintenance records for each plane
        last_maintenance_response = supabase.table("maintenance").select(
            "plane_id, maintenance_id, employee_id, maintenance_type, maintenance_date, notes"
        ).order("maintenance_date", desc=True).execute()
        

        last_maintenance_data = last_maintenance_response.data
        last_maintenance_records = {}
        
        for record in last_maintenance_data:
            plane_id = record["plane_id"]
            if plane_id not in last_maintenance_records:
                last_maintenance_records[plane_id] = record
        
        return list(last_maintenance_records.values())
    except Exception as e:
        raise HTTPException(status_code=400, detail=e.message)

@app.get("/maintenance/next", response_model=List[Maintenance])
async def get_next_maintenance(user: User = Depends(require_roles(["Employee", "Admin"]))):
    try:
        # Fetch the next maintenance records
        next_maintenance_response = supabase.table("maintenance").select(
            "plane_id, maintenance_id, employee_id, maintenance_type, maintenance_date, notes"
        ).gt("maintenance_date", datetime.utcnow().date()).execute()

        return next_maintenance_response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/available_seats/{flight_number}", response_model=List[str])
async def get_available_seats(flight_number: str):
    try:
        response = supabase.rpc("get_available_seats", {"flight_": flight_number}).execute()
    except Exception as e:

        raise HTTPException(status_code=400, detail=e.message)
    return [seat["seat_number"] for seat in response.data]


# General functions
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Add your logic to authenticate the user and return a token
    auth_response = supabase.table("person").select("*").eq("username", form_data.username).eq("password", form_data.password).execute()
    if auth_response.data:
        user = auth_response.data[0]
        access_token = create_access_token(data={"sub": user["ssn"]})
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")



# Endpoint to handle logout
@app.post("/logout")
async def logout(user: User = Depends(get_current_user), token: str = Depends(oauth2_scheme)):
    blacklist_token(token)
    return {"message": "Logged out successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app="main:app", reload=True)