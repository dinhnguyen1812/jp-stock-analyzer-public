FROM node:18-bullseye

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Expose Vite dev server port (default is 5173, or change to 3000)
EXPOSE 3000

# Start the Vite dev server
CMD ["npm", "run", "dev"]
