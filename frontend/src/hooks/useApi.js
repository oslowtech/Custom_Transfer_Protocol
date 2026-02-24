import { useCallback } from 'react';

const API_BASE = '/api';

export function useApi() {
  const request = useCallback(async (method, endpoint, body = null, params = null) => {
    try {
      let url = `${API_BASE}${endpoint}`;
      
      // Add query parameters
      if (params) {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
          searchParams.append(key, value);
        });
        url += `?${searchParams.toString()}`;
      }
      
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
      };
      
      if (body) {
        options.body = JSON.stringify(body);
      }
      
      const response = await fetch(url, options);
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }
      
      return response.json();
    } catch (error) {
      console.error(`API ${method} ${endpoint} failed:`, error);
      throw error;
    }
  }, []);
  
  const get = useCallback((endpoint, params = null) => {
    return request('GET', endpoint, null, params);
  }, [request]);
  
  const post = useCallback((endpoint, body = null, params = null) => {
    return request('POST', endpoint, body, params);
  }, [request]);
  
  const put = useCallback((endpoint, body = null) => {
    return request('PUT', endpoint, body);
  }, [request]);
  
  const del = useCallback((endpoint) => {
    return request('DELETE', endpoint);
  }, [request]);
  
  return { get, post, put, del };
}
