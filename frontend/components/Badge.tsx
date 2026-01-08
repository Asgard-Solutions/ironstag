import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { colors, borderRadius, spacing } from '../constants/theme';

interface BadgeProps {
  text: string;
  variant?: 'harvest' | 'pass' | 'info' | 'warning';
  size?: 'small' | 'medium';
  style?: ViewStyle;
}

export const Badge: React.FC<BadgeProps> = ({
  text,
  variant = 'info',
  size = 'medium',
  style,
}) => {
  return (
    <View style={[styles.badge, styles[variant], styles[`${size}Size`], style]}>
      <Text style={[styles.text, styles[`${variant}Text`], styles[`${size}Text`]]}>
        {text}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    borderRadius: borderRadius.full,
    alignSelf: 'flex-start',
  },
  harvest: {
    backgroundColor: colors.harvestBg,
  },
  pass: {
    backgroundColor: colors.passBg,
  },
  info: {
    backgroundColor: 'rgba(33, 150, 243, 0.15)',
  },
  warning: {
    backgroundColor: 'rgba(255, 193, 7, 0.15)',
  },
  smallSize: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  mediumSize: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  text: {
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  harvestText: {
    color: colors.harvest,
  },
  passText: {
    color: colors.pass,
  },
  infoText: {
    color: colors.info,
  },
  warningText: {
    color: colors.warning,
  },
  smallText: {
    fontSize: 10,
  },
  mediumText: {
    fontSize: 12,
  },
});
