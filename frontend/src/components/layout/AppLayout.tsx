import { Box, Flex } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";

import { TopBar } from "./TopBar";

export function AppLayout() {
  return (
    <Flex direction="column" height="100vh" overflow="hidden">
      <TopBar />

      <Box flex="1" minHeight={0} overflowY="auto" bg="gray.50">
        <Outlet />
      </Box>
    </Flex>
  );
}
