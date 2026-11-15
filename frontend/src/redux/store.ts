import {configureStore} from '@reduxjs/toolkit';
import {api} from './api';

export function makeStore() {
  return configureStore({
    reducer: {[api.reducerPath]: api.reducer},
    middleware: (getDefault) => getDefault().concat(api.middleware),
  });
}

export const store = makeStore();
