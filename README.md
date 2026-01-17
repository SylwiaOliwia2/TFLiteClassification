# About the app 
This is simple image recognition app (done for fun in a leasure time, vibe-coded with Cursor), which uses [TFLiteClassification
](https://github.com/joonb14/TFLiteClassification) models for image recognition.

It uses:
- Vue + Vite as a frontend
- FastApi as an API
- Redis + Celery + Tensorflow for image processing  

## Running the Web Application

The project includes a web application with a FastAPI backend and Vue.js frontend. To run it using Docker:

1. Make sure Docker and Docker Compose are installed on your system.

2. Build and start the services:
   ```bash
   docker-compose up --build
   ```

3. Access the application:
   - **Frontend**: Open your browser and navigate to http://localhost:5173
   - **Backend API**: Available at http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs (FastAPI auto-generated docs)

4. To stop the services:
   ```bash
   docker-compose down
   ```

The web application allows you to upload an image through the browser interface. Click "Tell me what is on the image" to send the image to the backend API, which will return classification results displayed in a table format.
