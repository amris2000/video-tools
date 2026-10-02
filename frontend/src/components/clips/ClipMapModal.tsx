import {
  Box,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Stack,
  Text,
} from "@chakra-ui/react";
import { Map, Marker } from "pigeon-maps";
import { type Clip } from "../../api/clips";

interface ClipMapModalProps {
  isOpen: boolean;
  onClose: () => void;
  clip: Clip | null;
}

export function ClipMapModal({ isOpen, onClose, clip }: ClipMapModalProps) {
  const gps = clip?.gps;
  const hasPosition =
    !!gps?.available &&
    typeof gps.latitude === "number" &&
    typeof gps.longitude === "number";

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="3xl" isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Clip location</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          {!clip || !hasPosition ? (
            <Text color="gray.600">No GPS location found for this clip.</Text>
          ) : (
            <Stack spacing={3}>
              <Text fontSize="sm" color="gray.600" overflowWrap="anywhere">
                {clip.path}
              </Text>

              <Box borderRadius="md" overflow="hidden" borderWidth="1px">
                <Map
                  height={360}
                  defaultCenter={[gps.latitude!, gps.longitude!]}
                  defaultZoom={13}
                >
                  <Marker
                    width={40}
                    anchor={[gps.latitude!, gps.longitude!]}
                    color="#2563eb"
                  />
                </Map>
              </Box>

              <Text fontSize="sm" color="gray.700">
                {gps.latitude!.toFixed(6)}, {gps.longitude!.toFixed(6)}
                {typeof gps.altitude === "number"
                  ? ` · Alt ${gps.altitude.toFixed(1)}m`
                  : ""}
              </Text>
            </Stack>
          )}
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
