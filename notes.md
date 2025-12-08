Task 1:
Google Sign-In & Paystack Payment — Task Requirements

The goal is to test your ability to build simple backend endpoints, integrate with third‑party services, and understand basic authentication and payment flows.

Aim
Implement backend-only Google Sign-In and Paystack payment functionalities, exposing secure, well-defined API endpoints that authenticate users, initiate payments, and provide reliable transaction status updates.

Objectives
 Understand how Google sign‑in works at a basic level.
 Make simple backend endpoints that call Google and Paystack.
 Save basic information to the database.
 Handle payment initiation and check payment status.

Scope (In-Scope)
 Backend-only endpoints and flows — no UI work required.
 Database schema for storing users and payments / transactions.
 Integration with Google OAuth 2.0 (server-side flow using client credentials).
 Integration with Paystack to create transactions and get transaction status using webhook or paystack’s verify transaction endpoint.

Out of Scope
 Frontend integration & UI components.
 Alternative payment providers other than Paystack.

High-Level Flow (Easy Description)
Google Sign‑In
 The user hits an endpoint.
 They get redirected to Google to log in.
 Google sends a code back to your callback endpoint.
 Your server exchanges that code for the user’s info.
 You save the user in the database.

Paystack Payment
 The user hits your “start payment” endpoint.
 Your server calls Paystack to initialize a transaction.
 Paystack sends back an authorization link.
 You return that link to the user.
 To check status, your server can:
 receive a webhook from Paystack, or
 call Paystack’s verify endpoint when someone asks.

API Endpoints (Specification)
1. Trigger Google sign-in flow
GET /auth/google
 Purpose: Return a redirect (302) to Google OAuth consent page or provide the URL in JSON.
 Response (redirect): 302 -> Google OAuth URL
 Response (JSON option): 200 { "google_auth_url": "https://accounts.google.com/...." }
 Errors: 400 invalid redirect, 500 on internal error


2. Google OAuth callback
GET /auth/google/callback
 Purpose:
 Exchange code for access token (server-to-server call to Google's token endpoint).
 Fetch userinfo from Google (openid, email, name, picture, etc.).
 Create or update a User record in the DB.
 Success Response: 200 JSON { "user_id": "...", "email": "...", "name": "..." }
 Errors: 400 missing code, 401 invalid code, 500 provider error

3. Initiate Paystack payment
POST /payments/paystack/initiate
Body JSON (example):
  {
    "amount": 5000,  // amount in Kobo (lowest currency unit)
  }
 Steps:
 Validate user and amount.
 Call Paystack Initialize Transaction API with secret key.
 Persist transaction with reference and initial status pending.
 Response: 201
 { 
   "reference": "...", 
   "authorization_url": "https://paystack.co/checkout/...." 
 }
 Errors: 400 invalid input, 402 payment initiation failed by Paystack, 500

4. Webhook endpoint (optional but recommended)
POST /payments/paystack/webhook
 Purpose: Receive transaction updates from Paystack.
 Security: Validate Paystack signature header (e.g. x-paystack-signature) using configured webhook secret.
 Steps:
 Verify signature.
 Parse event payload; find transaction reference.
 Update transaction status in DB (success, failed, pending, etc.).
 Response: 200
 {"status": true}
 Errors: 400 invalid signature, 500 server error

5. Check transaction status (on-demand)
GET /payments/{reference}/status
 Purpose: Return the latest status for reference.
 Behavior: Return DB status. If missing or caller requests refresh=true, call Paystack verify endpoint to fetch live status and update DB.
 Response: 200
 { 
   "reference": "...", 
   "status": "success|failed|pending", 
   "amount": 5000, 
   "paid_at": "..." 
 }

Security Considerations (Simple)
 Don’t expose your secret keys.
 Make sure only Google redirects back to your callback.
 Verify Paystack webhooks so strangers can’t fake payment updates.

Error Handling & Idempotency
 Use the reference as idempotency key for Paystack transactions. If duplicate initiation is detected, return the existing transaction to the initiator of the transaction only.
 Return clear error codes and messages.

Endpoints to Test:
1. GET /auth/google
Specification: Returns redirect (302) to Google OAuth URL OR JSON with URL

bash
# Test 1A: Get JSON response with Google auth URL
curl -X GET "http://localhost:8001/auth/google" \
     -H "Accept: application/json" \
     -H "Content-Type: application/json"

# Test 1B: Get 302 redirect (browser behavior)
curl -X GET "http://localhost:8001/auth/google" \
     -L -v  # -L follows redirects, -v shows verbose output
Expected Response 1A (JSON):

json
{
  "success": true,
  "message": "Google authentication URL generated",
  "data": {
    "google_auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=826732109697-ci8m4s9r5j01alce7uk86r9e709v55fj.apps.googleusercontent.com&redirect_uri=http://localhost:8001/auth/google/callback&response_type=code&scope=openid email profile&access_type=offline&prompt=consent"
  }
}
Expected Response 1B: 302 redirect to the Google URL

2. GET /auth/google/callback
Note: This is called by Google with a code parameter after user authentication

bash
# This endpoint is called by Google with ?code=XXX after user signs in
# You need to:
# 1. First visit /auth/google in browser
# 2. Sign in with Google
# 3. Google will redirect to: http://localhost:8001/auth/google/callback?code=AUTHORIZATION_CODE
# 4. Replace YOUR_GOOGLE_AUTH_CODE with actual code from browser URL

curl -X GET "http://localhost:8001/auth/google/callback?code=4%2F0ATX87lMdfyqHVS3kBEFKEMHnRfZ0NwZeTcu93BKmrk3ZLfBeWOzUgFoOwMimwb8BP7JChA" \
     -H "Content-Type: application/json"

     
Expected Success Response:

json
{
  "success": true,
  "message": "User authentication successful",
  "data": {
    "user_id": "UUID_FROM_DATABASE",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
Save this user_id for the next endpoint.

3. POST /payments/paystack/initiate
Specification: Body requires only amount in Kobo

bash
# Replace USER_ID_FROM_PREVIOUS_STEP with actual user_id from Google auth response
curl -X POST "http://localhost:8001/payments/paystack/initiate" \
     -H "Content-Type: application/json" \
     -d '{
       "amount": 5000,
       "user_id": "USER_ID_FROM_PREVIOUS_STEP"
     }'
Expected Success Response (201 Created):

json
{
  "success": true,
  "message": "Payment initialized successfully",
  "data": {
    "reference": "TXN_USER_ID_TIMESTAMP",
    "authorization_url": "https://checkout.paystack.com/UNIQUE_CHECKOUT_CODE"
  }
}
Save this reference for the next endpoint.

4. GET /payments/{reference}/status
Specification: Check transaction status, optional refresh=true parameter

bash
# Replace TRANSACTION_REFERENCE with reference from previous step
curl -X GET "http://localhost:8001/payments/TRANSACTION_REFERENCE/status" \
     -H "Content-Type: application/json"

# With refresh parameter (forces Paystack verification)
curl -X GET "http://localhost:8001/payments/TRANSACTION_REFERENCE/status?refresh=true" \
     -H "Content-Type: application/json"
Expected Response:

json
{
  "success": true,
  "message": "Transaction status retrieved",
  "data": {
    "reference": "TXN_USER_ID_TIMESTAMP",
    "status": "pending|success|failed|abandoned",
    "amount": 5000,
    "paid_at": "2024-01-01T12:00:00Z"  # null if not paid
  }
}
5. POST /payments/paystack/webhook
Specification: Paystack calls this with webhook data. Needs signature validation.

bash
# This is called by PAYSTACK, not by you directly
# But for testing, you can simulate a webhook:

# Replace WEBHOOK_SECRET from your .env file
# Replace PAYSTACK_SIGNATURE from Paystack headers
# Replace TRANSACTION_REFERENCE with actual Paystack reference

curl -X POST "http://localhost:8001/payments/paystack/webhook" \
     -H "Content-Type: application/json" \
     -H "x-paystack-signature: GENERATED_SIGNATURE_FROM_PAYSTACK" \
     -d '{
       "event": "charge.success",
       "data": {
         "reference": "PAYSTACK_REFERENCE",
         "status": "success",
         "amount": 5000,
         "paid_at": "2024-01-01T12:00:00Z"
       }
     }'
Expected Response:

json
{
  "success": true,
  "message": "Webhook processed",
  "data": {}
}