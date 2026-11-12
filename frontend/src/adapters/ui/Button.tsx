import { createButton } from '@gluestack-ui/core/button/creator';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

export const Button = createButton({
  Root: Pressable,
  Text,
  Group: View,
  Spinner: ActivityIndicator,
  Icon: View,
});
