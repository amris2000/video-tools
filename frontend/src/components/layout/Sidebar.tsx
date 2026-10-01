import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Button, Stack, Text, VStack } from "@chakra-ui/react";

import {
  FiFilm,
  FiFolder,
  FiHome,
  FiImage,
  FiBookOpen,
  FiUpload,
  FiShare2,
} from "react-icons/fi";

const navigation = [
  {
    label: "Overview",
    icon: FiHome,
  },
  {
    label: "Clips",
    icon: FiFilm,
  },
  {
    label: "Import",
    icon: FiUpload,
  },
  {
    label: "Editor",
    icon: FiImage,
  },
  {
    label: "Renders",
    icon: FiFolder,
  },
  {
    label: "Social Export",
    icon: FiShare2,
  },
  {
    label: "Journal",
    icon: FiBookOpen,
  },
];

export function Sidebar() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  return (
    <VStack
      as="nav"
      width="240px"
      minWidth="240px"
      height="100%"
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

      <Stack spacing={1}>
        {navigation.map((item) => (
          <Button
            key={item.label}
            isDisabled={!["Overview", "Clips"].includes(item.label)}
            isActive={["Overview", "Clips"].includes(item.label) && pathname === "/projects/" + projectId + (item.label === "Clips" ? "/clips" : "")}
            onClick={() => navigate("/projects/" + projectId + (item.label === "Clips" ? "/clips" : ""))}
            leftIcon={<item.icon />}
            justifyContent="flex-start"
            variant="ghost"
          >
            {item.label}
          </Button>
        ))}
      </Stack>
    </VStack>
  );
}
