import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import {Provider} from 'react-redux';
import {App} from './App';
import './index.css';
import {store} from './redux/store';

const root = document.getElementById('root');
if (!root) throw new Error('missing #root');

createRoot(root).render(
  <StrictMode>
    <Provider store={store}>
      <App />
    </Provider>
  </StrictMode>,
);
