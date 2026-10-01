import { Box, Flex } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "./Sidebar";

export function ProjectLayout() {
  return (
    <Flex height="100%" minHeight={0} direction={{ base: "column", md: "row" }}>
      <Sidebar />

      <Box as="main" flex="1" minWidth={0} overflowY="auto" bg="gray.50">
        <Box
          width="100%"
          maxWidth="1400px"
          minHeight="100%"
          mx="auto"
          p={{ base: 4, md: 8 }}
        >
          <Outlet />
        </Box>
      </Box>
    </Flex>
  );
}
