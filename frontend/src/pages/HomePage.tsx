import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Container,
  Heading,
  HStack,
  SimpleGrid,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useNavigate } from "react-router-dom";

import { useProjects } from "../context/ProjectContext";

export function HomePage() {
  const navigate = useNavigate();

  const { projects, loading, error, refreshProjects } = useProjects();

  if (loading) {
    return (
      <Container maxW="6xl" py={12}>
        <HStack>
          <Spinner />
          <Text>Discovering projects...</Text>
        </HStack>
      </Container>
    );
  }

  return (
    <Container maxW="6xl" py={12}>
      <VStack align="stretch" spacing={8}>
        <HStack justify="space-between">
          <Box>
            <Heading size="lg">Video Tools</Heading>

            <Text mt={2} color="gray.500">
              Select a video project to continue.
            </Text>
          </Box>

          <HStack>
            <Button variant="outline" onClick={() => void refreshProjects()}>
              Refresh
            </Button>

            <Button variant="outline" onClick={() => navigate("/settings")}>
              Settings
            </Button>
          </HStack>
        </HStack>

        {error && (
          <Alert status="error">
            <AlertIcon />
            {error}
          </Alert>
        )}

        {!error && projects.length === 0 && (
          <Box borderWidth="1px" borderRadius="lg" bg="white" p={8}>
            <Heading size="md">No projects found</Heading>

            <Text mt={2} color="gray.500">
              No Video Tools projects were discovered in the configured folder.
            </Text>
          </Box>
        )}

        <SimpleGrid
          columns={{
            base: 1,
            md: 2,
            lg: 3,
          }}
          spacing={4}
        >
          {projects.map((project) => (
            <Box
              key={project.id}
              borderWidth="1px"
              borderRadius="lg"
              bg="white"
              p={6}
              cursor="pointer"
              _hover={{
                shadow: "md",
                borderColor: "brand.300",
              }}
              onClick={() => navigate(`/projects/${project.id}`)}
            >
              <Heading size="md">{project.name}</Heading>

              <Text mt={2} fontSize="sm" color="gray.500" noOfLines={1}>
                {project.path}
              </Text>
            </Box>
          ))}
        </SimpleGrid>
      </VStack>
    </Container>
  );
}
