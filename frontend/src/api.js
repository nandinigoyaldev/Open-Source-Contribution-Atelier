import axios from 'axios';

const api = axios.create({
  // This matches your Django server's address
  baseURL: 'http://127.0.0.1:8000/api/', 
});

export default api;