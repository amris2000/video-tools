import { extendTheme } from "@chakra-ui/react";

const theme = extendTheme({
  styles: {
    global: {
      "html, body, #root": {
        minHeight: "100%",
      },
      body: {
        bg: "gray.50",
        color: "gray.900",
      },
    },
  },

  colors: {
    brand: {
      50: "#eef2ff",
      100: "#e0e7ff",
      200: "#c7d2fe",
      300: "#a5b4fc",
      400: "#818cf8",
      500: "#6366f1",
      600: "#4f46e5",
      700: "#4338ca",
      800: "#3730a3",
      900: "#312e81",
    },
  },
});

export default theme;
