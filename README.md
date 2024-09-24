# Drip Advisor Backend
Drip Advisor is an AI-powered fashion assistant that helps users find the perfect outfit from their wardrobe. This repository contains the backend code for the Drip Advisor application. The backend is built using Flask and deployed on Vercel.

## Demo

https://drip-advisor-backend.vercel.app/


## Running Locally

```bash
npm i -g vercel
vercel dev
```

Your Flask application is now available at http://localhost:3000.

---

# Drip Advisor Backend API User Guide

Base URL: `https://drip-advisor-backend.vercel.app`

## Authentication

Most endpoints require JWT authentication. Include the JWT token in the Authorization header for all authenticated requests:

```
Authorization: Bearer <your_jwt_token>
```

### Sign Up
- **URL:** `/users/signup`
- **Method:** POST
- **Authentication:** Not required
- **Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "your_password",
    "name": "Your Name",
    "gender": "your_gender",
    "dob": "YYYY-MM-DD"
  }
  ```
- **Response:** User created message with ID

### Login
- **URL:** `/users/login`
- **Method:** POST
- **Authentication:** Not required
- **Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "your_password"
  }
  ```
- **Response:** JWT access token

## User Profile

### Get Profile
- **URL:** `/users/profile`
- **Method:** GET
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Response:** User profile data

### Update Profile
- **URL:** `/users/profile`
- **Method:** PUT
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Body:**
  ```json
  {
    "name": "Updated Name",
    "gender": "updated_gender",
    "dob": "YYYY-MM-DD"
  }
  ```
- **Response:** Profile updated message

### Delete Profile
- **URL:** `/users/profile`
- **Method:** DELETE
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Response:** Profile deleted message

### Add Preferences
- **URL:** `/users/preferences`
- **Method:** POST
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Body:**
  ```json
  {
    "preferences": ["preference1", "preference2"]
  }
  ```
- **Response:** Preferences added message

## Clothing Items

### Add Clothing Item
- **URL:** `/add_clothing_item`
- **Method:** POST
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Body:** Form-data with 'image' file
- **Response:** Clothing item added message with ID

### Get Clothing Item
- **URL:** `/clothing_items`
- **Method:** GET
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Body:**
  ```json
  {
    "clothing_item_id": "item_id_here"
  }
  ```
- **Response:** Clothing item details

## Outfits

### Generate Outfit
- **URL:** `/outfits/generate`
- **Method:** POST
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Body:**
  ```json
  {
    "weather_description": "sunny day with high humidity",
    "temperature": "27",
    "day_description": "Lunch with friends and meeting with nature club"
  }
  ```
- **Response:** Array of generated outfits

### Build Outfit
- **URL:** `/outfits/build`
- **Method:** POST
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Body:**
  ```json
  {
    "weather_description": "sunny day with high humidity",
    "temperature": "27",
    "day_description": "Lunch with friends and meeting with nature club",
    "base_items_ids": ["66f049d6f6d2352521cf0221"]
  }
  ```
- **Response:** Array of generated outfits based on specified items

### Get All Outfits
- **URL:** `/outfits`
- **Method:** GET
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Response:** Array of all user's outfits

### Get Outfit by ID
- **URL:** `/outfits/<outfit_id>`
- **Method:** GET
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Response:** Specific outfit details

### Use Outfit
- **URL:** `/outfits/use/<outfit_id>`
- **Method:** POST
- **Authentication:** Required
  - Header: `Authorization: Bearer <your_jwt_token>`
- **Response:** Outfit used message (marks items as unavailable for 48 hours)

## Miscellaneous

### Generate Tags
- **URL:** `/generate_tags`
- **Method:** POST
- **Authentication:** Not required
- **Body:** Form-data with 'image' file
- **Response:** Generated description for the clothing item

### Ask Gemini
- **URL:** `/gemini`
- **Method:** POST
- **Authentication:** Not required
- **Body:**
  ```json
  {
    "prompt": "Your question or prompt here"
  }
  ```
- **Response:** Gemini AI-generated response

## Error Handling

All endpoints return appropriate error messages and status codes in case of failures. Check the response status code and error message for troubleshooting.
