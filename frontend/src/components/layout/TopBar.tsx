import {
  Box,
  Button,
  Flex,
  HStack,
  Select,
  Spacer,
  Text,
} from "@chakra-ui/react";
import { LuClapperboard } from "react-icons/lu";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { useProjects } from "../../context/ProjectContext";

export function TopBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId } = useParams();

  const { projects } = useProjects();

  const projectSelected = projectId !== undefined;

  return (
    <Flex
      as="header"
      height="64px"
      minHeight="64px"
      align="center"
      px={6}
      bg="white"
      borderBottomWidth="1px"
    >
      <HStack spacing={3}>
        <Box
          display="flex"
          alignItems="center"
          justifyContent="center"
          color="brand.500"
          fontSize="22px"
        >
          <LuClapperboard />
        </Box>

        <Text fontSize="lg" fontWeight="semibold" whiteSpace="nowrap">
          Amris Video Tools
        </Text>

        <Box
          height="24px"
          borderLeftWidth="1px"
          borderColor="gray.200"
          mx={2}
        />

        <Button
          variant={location.pathname === "/" ? "solid" : "ghost"}
          colorScheme={location.pathname === "/" ? "brand" : undefined}
          onClick={() => navigate("/")}
        >
          Projects
        </Button>
      </HStack>

      <Spacer />

      <HStack spacing={3}>
        {projectSelected && (
          <Select
            value={projectId}
            onChange={(event) => {
              const nextProjectId = event.target.value;

              if (nextProjectId) {
                navigate(`/projects/${nextProjectId}`);
              }
            }}
            width="220px"
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </Select>
        )}

        <Button variant="ghost" onClick={() => navigate("/settings")}>
          Settings
        </Button>
      </HStack>
    </Flex>
  );
}
