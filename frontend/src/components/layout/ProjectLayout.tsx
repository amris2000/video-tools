import { Box, Flex } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "./Sidebar";

export function ProjectLayout() {
  return (
    <Flex height="100%" minHeight={0}>
      <Sidebar />

      <Box as="main" flex="1" overflowY="auto" bg="gray.50" p={8}>
        <Outlet />
      </Box>
    </Flex>
  );
}
