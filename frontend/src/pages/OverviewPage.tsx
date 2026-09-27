import {
  Alert,
  AlertIcon,
  Heading,
  HStack,
  SimpleGrid,
  Spinner,
  Stat,
  StatLabel,
  StatNumber,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getProject, type ProjectDetails } from "../api/projects";

export function OverviewPage() {
  const { projectId } = useParams();

  const [project, setProject] = useState<ProjectDetails | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      setError("No project selected.");
      setLoading(false);
      return;
    }

    async function loadProject() {
      try {
        setLoading(true);
        setError(null);

        const details = await getProject(projectId!);

        setProject(details);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Could not load project.",
        );
      } finally {
        setLoading(false);
      }
    }

    void loadProject();
  }, [projectId]);

  if (loading) {
    return (
      <HStack>
        <Spinner />
        <Text>Loading project...</Text>
      </HStack>
    );
  }

  if (error || !project) {
    return (
      <Alert status="error">
        <AlertIcon />
        {error ?? "Project not found."}
      </Alert>
    );
  }

  return (
    <VStack align="stretch" spacing={8}>
      <div>
        <Heading size="lg">{project.name}</Heading>

        <Text mt={2} color="gray.500">
          {project.path}
        </Text>

        {project.timezone && (
          <Text mt={2} fontSize="sm" color="gray.500">
            Timezone: {project.timezone}
          </Text>
        )}
      </div>

      <SimpleGrid
        columns={{
          base: 1,
          md: 2,
          lg: 4,
        }}
        spacing={4}
      >
        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Clips</StatLabel>
          <StatNumber>{project.stats.clips}</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Edits</StatLabel>
          <StatNumber>{project.stats.edits}</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Renders</StatLabel>
          <StatNumber>{project.stats.renders}</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Social exports</StatLabel>
          <StatNumber>{project.stats.social_exports}</StatNumber>
        </Stat>
      </SimpleGrid>
    </VStack>
  );
}
