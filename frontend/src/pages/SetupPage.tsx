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
  Input,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { updateConfig } from "../api/config";
import { useAppConfig } from "../context/AppConfigContext";

export function SetupPage() {
  const navigate = useNavigate();

  const { setConfig } = useAppConfig();

  const [projectsDirectory, setProjectsDirectory] = useState("");

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
      const config = await updateConfig({
        projects_directory: directory,
      });

      setConfig(config);

      navigate("/", {
        replace: true,
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not save configuration.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Container maxW="lg" py={20}>
      <Box bg="white" borderWidth="1px" borderRadius="xl" p={8}>
        <form onSubmit={handleSubmit}>
          <VStack align="stretch" spacing={6}>
            <Box>
              <Heading size="lg">Welcome to Video Tools</Heading>

              <Text mt={2} color="gray.500">
                Choose the folder containing your Video Tools projects.
              </Text>
            </Box>

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
                placeholder="C:\\Users\\Frederik\\Videos"
                autoFocus
              />

              <FormHelperText>
                Video Tools will discover projects inside this folder.
              </FormHelperText>
            </FormControl>

            <Button
              type="submit"
              colorScheme="brand"
              isLoading={saving}
              loadingText="Saving"
            >
              Save & Continue
            </Button>
          </VStack>
        </form>
      </Box>
    </Container>
  );
}
