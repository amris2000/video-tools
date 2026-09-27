import {
  Heading,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Text,
  HStack,
  VStack,
} from "@chakra-ui/react";
import { useParams } from "react-router-dom";

import { useProjects } from "../context/ProjectContext";

export function OverviewPage() {
  const { projectId } = useParams();
  const { projects } = useProjects();

  const project = projects.find((project) => project.id === projectId);

  if (!project) {
    return (
      <VStack align="stretch" spacing={2}>
        <Heading size="lg">Project not found</Heading>

        <Text color="gray.500">The requested project could not be found.</Text>
      </VStack>
    );
  }

  return (
    <VStack align="stretch" spacing={8}>
      <div>
        <div>
          <Heading size="lg">{project.name}</Heading>

          <Text mt={2} color="gray.500">
            {project.path}
          </Text>

          <HStack mt={2} spacing={4}>
            {project.timezone && (
              <Text fontSize="sm" color="gray.500">
                Timezone: {project.timezone}
              </Text>
            )}
          </HStack>
        </div>

        <Text mt={2} color="gray.500">
          {project.path}
        </Text>
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
          <StatNumber>—</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Edits</StatLabel>
          <StatNumber>—</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Renders</StatLabel>
          <StatNumber>—</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Social exports</StatLabel>
          <StatNumber>—</StatNumber>
        </Stat>
      </SimpleGrid>
    </VStack>
  );
}
