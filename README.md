# Garnet Web Visualizer

A simple streamlit application to adjust garnet configurations, run a simulation, and graph the output.

### How to Run

Download the `Dockerfile` and navigate to the directory containing it, then run:
```
docker build -t garnet-visualizer-app .
```

After building the docker container you can run the app using:
```
docker run -p 8501:8501 garnet-visualizer-app
```

Go to http://localhost:8501/ to see your running app.