import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  Button,
  Divider,
  Stack,
  Text,
  VStack,
  useDisclosure,
} from "@chakra-ui/react";
import { useRef, useState } from "react";

import {
  FiFilm,
  FiFolder,
  FiHome,
  FiEdit3,
  FiDownload,
  FiPlayCircle,
  FiBookOpen,
} from "react-icons/fi";
import { deleteProject } from "../../api/projects";
import { useProjects } from "../../context/ProjectContext";

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
    label: "Import",
    icon: FiDownload,
    path: "/import",
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
  {
    label: "Journal",
    icon: FiBookOpen,
    path: "/journal",
    enabled: true,
  },
];

export function Sidebar() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { refreshProjects } = useProjects();
  const { isOpen, onOpen, onClose } = useDisclosure();

  const cancelRef = useRef<HTMLButtonElement>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const projectBasePath = `/projects/${projectId}`;

  async function handleDeleteProject() {
    if (!projectId || deleting) {
      return;
    }

    setDeleting(true);
    setDeleteError(null);

    try {
      await deleteProject(projectId);
      await refreshProjects();
      onClose();
      navigate("/");
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : "Could not delete project.",
      );
    } finally {
      setDeleting(false);
    }
  }

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

      <Divider my={4} />

      <Button
        colorScheme="red"
        variant="outline"
        onClick={() => {
          setDeleteError(null);
          onOpen();
        }}
      >
        Delete project
      </Button>

      <AlertDialog
        isOpen={isOpen}
        leastDestructiveRef={cancelRef}
        onClose={() => {
          if (!deleting) {
            onClose();
          }
        }}
        isCentered
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete project
            </AlertDialogHeader>

            <AlertDialogBody>
              <VStack align="stretch" spacing={4}>
                <Alert status="warning" borderRadius="md">
                  <AlertIcon />
                  <VStack align="stretch" spacing={1}>
                    <AlertTitle>Are you sure?</AlertTitle>
                    <AlertDescription>
                      This will permanently remove the project directory and all
                      files inside it.
                    </AlertDescription>
                  </VStack>
                </Alert>

                {projectId && (
                  <Text fontSize="sm" color="gray.600">
                    Project id: {projectId}
                  </Text>
                )}

                {deleteError && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    {deleteError}
                  </Alert>
                )}
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onClose} isDisabled={deleting}>
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={() => void handleDeleteProject()}
                ml={3}
                isLoading={deleting}
              >
                Delete project
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
}
