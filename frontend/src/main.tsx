import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ChakraProvider } from "@chakra-ui/react";

import App from "./App";
import theme from "./theme";
import { AppConfigProvider } from "./context/AppConfigContext";
import { ProjectProvider } from "./context/ProjectContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ChakraProvider theme={theme}>
        <AppConfigProvider>
          <ProjectProvider>
            <App />
          </ProjectProvider>
        </AppConfigProvider>
      </ChakraProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
