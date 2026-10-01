import { AspectRatio, Box, Checkbox, Image, Text, VStack } from "@chakra-ui/react";
import { type Clip } from "../../api/clips";

interface ClipCardProps {
  clip: Clip;
  selected?: boolean;
  onToggle?: () => void;
}

export function ClipCard({ clip, selected = false, onToggle }: ClipCardProps) {
  const duration = clip.duration === null ? null : Math.floor(clip.duration / 60) + ":" + String(Math.floor(clip.duration % 60)).padStart(2, "0");
  const metadata = [
    duration,
    clip.width && clip.height ? clip.width + " × " + clip.height : null,
    clip.fps ? clip.fps + " fps" : null,
  ].filter(Boolean).join(" · ");

  return (
    <Box as="article" bg="white" borderWidth="2px" borderColor={selected ? "blue.500" : "gray.200"} borderRadius="lg" overflow="hidden">
      <AspectRatio ratio={16 / 9} bg="gray.100">
        {clip.thumbnail_url ? (
          <Image src={clip.thumbnail_url} alt="" loading="lazy" objectFit="cover"
            fallback={<Text color="gray.500">No thumbnail</Text>} />
        ) : <Text color="gray.500">No thumbnail</Text>}
      </AspectRatio>
      <VStack align="stretch" p={4} spacing={2}>
        {onToggle ? (
          <Checkbox isChecked={selected} onChange={onToggle} colorScheme="blue">
            <Text fontWeight="semibold" overflowWrap="anywhere">{clip.name}</Text>
          </Checkbox>
        ) : <Text fontWeight="semibold" overflowWrap="anywhere">{clip.name}</Text>}
        <Text fontSize="xs" color="gray.500" overflowWrap="anywhere">{clip.path}</Text>
        <Text fontSize="sm" color="gray.600">{metadata || "Metadata unavailable"}</Text>
        {clip.creation_time && <Text fontSize="xs" color="gray.600">{clip.creation_time.replace("T", " ")}</Text>}
      </VStack>
    </Box>
  );
}
