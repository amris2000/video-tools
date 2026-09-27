import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Container,
  FormControl,
  FormHelperText,
  FormLabel,
  Heading,
  HStack,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { updateConfig } from "../api/config";
import { useAppConfig } from "../context/AppConfigContext";
import { useProjects } from "../context/ProjectContext";

export function SettingsPage() {
  const navigate = useNavigate();

  const { config, setConfig } = useAppConfig();

  const { refreshProjects } = useProjects();

  const [projectsDirectory, setProjectsDirectory] = useState(
    config?.projects_directory ?? "",
  );

  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const directory = projectsDirectory.trim();

    if (!directory) {
      setError("Enter a projects folder.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const updatedConfig = await updateConfig({
        projects_directory: directory,
      });

      setConfig(updatedConfig);

      await refreshProjects();

      navigate("/", {
        replace: true,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Container maxW="2xl" py={12}>
      <VStack align="stretch" spacing={8}>
        <Box>
          <Heading size="lg">Settings</Heading>

          <Text mt={2} color="gray.500">
            Configure Video Tools.
          </Text>
        </Box>

        <Box
          as="form"
          onSubmit={handleSubmit}
          borderWidth="1px"
          borderRadius="xl"
          bg="white"
          p={8}
        >
          <VStack align="stretch" spacing={6}>
            {error && (
              <Alert status="error">
                <AlertIcon />
                {error}
              </Alert>
            )}

            <FormControl isRequired>
              <FormLabel>Projects folder</FormLabel>

              <Input
                value={projectsDirectory}
                onChange={(event) => setProjectsDirectory(event.target.value)}
              />

              <FormHelperText>
                Video Tools discovers projects inside this folder.
              </FormHelperText>
            </FormControl>

            <HStack justify="flex-end">
              <Button
                type="button"
                variant="ghost"
                onClick={() => navigate(-1)}
              >
                Cancel
              </Button>

              <Button
                type="submit"
                colorScheme="brand"
                isLoading={saving}
                loadingText="Saving"
              >
                Save
              </Button>
            </HStack>
          </VStack>
        </Box>
      </VStack>
    </Container>
  );
}
