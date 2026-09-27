import { Center, Spinner, Text, VStack } from "@chakra-ui/react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAppConfig } from "../context/AppConfigContext";

export function AppBootstrap() {
  const location = useLocation();

  const { config, loading, error } = useAppConfig();

  if (loading) {
    return (
      <Center height="100vh">
        <VStack spacing={4}>
          <Spinner size="lg" />

          <Text color="gray.500">Starting Video Tools...</Text>
        </VStack>
      </Center>
    );
  }

  if (error) {
    return (
      <Center height="100vh">
        <VStack spacing={2}>
          <Text fontWeight="bold">Could not start Video Tools</Text>

          <Text color="red.500">{error}</Text>
        </VStack>
      </Center>
    );
  }

  if (!config?.configured && location.pathname !== "/setup") {
    return <Navigate to="/setup" replace />;
  }

  if (config?.configured && location.pathname === "/setup") {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
