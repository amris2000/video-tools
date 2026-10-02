import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Container,
  Heading,
  HStack,
  Input,
  SimpleGrid,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createProject } from "../api/projects";
import { useProjects } from "../context/ProjectContext";
import { useAppConfig } from "../context/AppConfigContext";

export function HomePage() {
  const navigate = useNavigate();
  const { config } = useAppConfig();

  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const { projects, loading, error, refreshProjects } = useProjects();

  async function handleCreateProject() {
    if (creating) {
      return;
    }

    setCreating(true);
    setCreateError(null);

    try {
      const created = await createProject({
        name: newProjectName,
      });

      await refreshProjects();
      setNewProjectName("");
      setShowCreateForm(false);
      navigate(`/projects/${created.id}`);
    } catch (err) {
      setCreateError(
        err instanceof Error ? err.message : "Could not create project.",
      );
    } finally {
      setCreating(false);
    }
  }

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
            <Heading size="lg">Projects</Heading>

            <Text mt={2} color="gray.500">
              Select a video project to continue.
            </Text>

            {config?.projects_directory && (
              <Text mt={1} fontSize="sm" color="gray.500">
                Directory: {config.projects_directory}
              </Text>
            )}
          </Box>

          <HStack>
            <Button
              onClick={() => {
                setShowCreateForm((visible) => !visible);
                setCreateError(null);
              }}
            >
              {showCreateForm ? "Close" : "New project"}
            </Button>

            <Button variant="outline" onClick={() => void refreshProjects()}>
              Refresh
            </Button>
          </HStack>
        </HStack>

        {showCreateForm && (
          <Box borderWidth="1px" borderRadius="lg" bg="white" p={5}>
            <VStack align="stretch" spacing={3}>
              <Heading size="sm">Create project</Heading>

              <Text color="gray.500" fontSize="sm">
                Enter a project folder name to create under the configured
                projects directory.
              </Text>

              <Input
                placeholder="Example: portugal-2027"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
              />

              {createError && (
                <Alert status="error">
                  <AlertIcon />
                  {createError}
                </Alert>
              )}

              <HStack justify="flex-end">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowCreateForm(false);
                    setCreateError(null);
                  }}
                >
                  Cancel
                </Button>

                <Button
                  colorScheme="brand"
                  isLoading={creating}
                  onClick={() => void handleCreateProject()}
                >
                  Create project
                </Button>
              </HStack>
            </VStack>
          </Box>
        )}

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
