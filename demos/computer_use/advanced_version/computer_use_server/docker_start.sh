
docker build -t computer_use_agent .

docker run -d \
  --env-file .env \
  -p 7860:7860 \
  computer_use_agent