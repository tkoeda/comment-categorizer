import Dashboard from './components/Dashboard'
import './App.css'
import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";

import "@mantine/core/styles.css"; 
import "@mantine/notifications/styles.css";

function App() {
  return (
      <MantineProvider>
          <Notifications />
          <Dashboard />
      </MantineProvider>
  );
};

export default App
