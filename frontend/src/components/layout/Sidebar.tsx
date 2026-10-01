import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Button, Stack, Text, VStack } from "@chakra-ui/react";

import {
  FiFilm,
  FiFolder,
  FiHome,
  FiEdit3,
  FiPlayCircle,
} from "react-icons/fi";

const navigation = [
  {
    label: "Overview",
    icon: FiHome,
    path: "",
    enabled: true,
  },
  {
    label: "Clips",
    icon: FiFilm,
    path: "/clips",
    enabled: true,
  },
  {
    label: "Editor",
    icon: FiEdit3,
    path: "/editor",
    enabled: true,
  },
  {
    label: "Render",
    icon: FiPlayCircle,
    path: "/render",
    enabled: true,
  },
  {
    label: "Exports",
    icon: FiFolder,
    path: "/exports",
    enabled: true,
  },
];

export function Sidebar() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const projectBasePath = `/projects/${projectId}`;

  return (
    <VStack
      as="nav"
      width={{ base: "100%", md: "240px" }}
      minWidth={{ base: 0, md: "240px" }}
      height={{ base: "auto", md: "100%" }}
      align="stretch"
      spacing={1}
      px={3}
      py={5}
      borderRightWidth="1px"
      bg="white"
    >
      <Text
        px={3}
        pb={2}
        fontSize="xs"
        fontWeight="bold"
        color="gray.400"
        textTransform="uppercase"
      >
        Project
      </Text>

      <Stack
        spacing={1}
        direction={{ base: "row", md: "column" }}
        overflowX={{ base: "auto", md: "visible" }}
      >
        {navigation.map((item) => {
          const target = `${projectBasePath}${item.path}`;

          return (
            <Button
              key={item.label}
              isDisabled={!item.enabled}
              isActive={item.enabled && pathname === target}
              onClick={() => navigate(target)}
              leftIcon={<item.icon />}
              justifyContent="flex-start"
              variant="ghost"
            >
              {item.label}
            </Button>
          );
        })}
      </Stack>
    </VStack>
  );
}
