import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Image,
  TextInput,
  ScrollView,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import { Search, Filter, X, Camera, Crown, Target, AlertCircle, MessageSquare } from 'lucide-react-native';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { useAuthStore } from '../../stores/authStore';
import { useImageStore } from '../../stores/imageStore';
import { scanAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { format, differenceInDays } from 'date-fns';

// ============ CONFIDENCE CALIBRATION CONSTANTS ============
// Cap confidence at this value when age is uncertain/unknown
const UNCERTAIN_AGE_CONFIDENCE_CAP = 60;

interface Scan {
  id: string;
  local_image_id: string;
  deer_age: number | null;
  deer_type: string | null;
  deer_sex: string | null;
  antler_points: number | null;
  antler_points_left: number | null;
  antler_points_right: number | null;
  body_condition: string | null;
  confidence: number | null;
  recommendation: string | null;
  notes: string | null;
  created_at: string;
  // Cloud image storage (R2) - for cross-device access
  image_url?: string | null;
}

// ============ CONFIDENCE & AGE UNCERTAINTY HELPERS ============

/**
 * Check if the age is uncertain/unknown
 * Age is considered uncertain if:
 * - It's null or undefined
 * - It's 0 (invalid age)
 * - It's a very low value that indicates estimation failure
 */
function isAgeUncertain(age: number | null | undefined): boolean {
  return age === null || age === undefined || age === 0;
}

/**
 * Get display-calibrated confidence value
 * If age is uncertain, cap confidence at UNCERTAIN_AGE_CONFIDENCE_CAP
 * This is a UI-level guardrail - does not modify backend data
 */
function getCalibratedConfidence(rawConfidence: number | null, age: number | null): number {
  const confidence = rawConfidence || 0;
  
  if (isAgeUncertain(age)) {
    return Math.min(confidence, UNCERTAIN_AGE_CONFIDENCE_CAP);
  }
  
  return confidence;
}

/**
 * Get age display text with uncertainty handling
 * Returns user-friendly text instead of "? yrs"
 */
function getAgeDisplayText(age: number | null): string {
  if (isAgeUncertain(age)) {
    return 'Uncertain';
  }
  return `${age} yrs`;
}

// Component to handle async image loading
function ScanImage({ localImageId, imageUrl }: { localImageId: string; imageUrl?: string | null }) {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const { getImage } = useImageStore();

  useEffect(() => {
    let mounted = true;
    
    const loadImage = async () => {
      try {
        // Try local image first
        const uri = await getImage(localImageId);
        if (mounted && uri) {
          setImageUri(uri);
        } else if (mounted && imageUrl) {
          // Fall back to cloud URL (R2) for cross-device access
          setImageUri(imageUrl);
        }
      } catch (error) {
        // If local image fails, try cloud URL
        if (mounted && imageUrl) {
          setImageUri(imageUrl);
        } else {
          console.error('Failed to load image:', error);
        }
      }
    };

    if (localImageId) {
      loadImage();
    } else if (imageUrl) {
      // No local image ID, use cloud URL directly
      setImageUri(imageUrl);
    }

    return () => {
      mounted = false;
    };
  }, [localImageId, imageUrl]);

  if (!imageUri) {
    return (
      <View style={styles.scanIconBox}>
        <Target size={28} color={colors.textPrimary} />
      </View>
    );
  }

  return <Image source={{ uri: imageUri }} style={styles.thumbnail} />;
}

export default function HistoryScreen() {
  const insets = useSafeAreaInsets();
  const { isAuthenticated, user } = useAuthStore();
  
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    deer_sex: '',
    recommendation: '',
  });
  
  // Track which scans have labels (for feedback badge)
  const [labeledScanIds, setLabeledScanIds] = useState<Set<string>>(new Set());

  const loadScans = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const response = await scanAPI.getScans({});
      setScans(response.data);
      
      // Check labels for scans >7 days old (for feedback badge)
      const eligibleScans = response.data.filter((scan: Scan) => {
        const daysSinceScan = differenceInDays(new Date(), new Date(scan.created_at));
        return daysSinceScan >= 7;
      });
      
      // Batch check labels for eligible scans (non-blocking)
      if (eligibleScans.length > 0) {
        const labelChecks = await Promise.allSettled(
          eligibleScans.map((scan: Scan) => scanAPI.getLabel(scan.id))
        );
        
        const labeled = new Set<string>();
        labelChecks.forEach((result, index) => {
          if (result.status === 'fulfilled' && result.value.data) {
            labeled.add(eligibleScans[index].id);
          }
        });
        setLabeledScanIds(labeled);
      }
    } catch (error) {
      console.error('Failed to load scans:', error);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  // Refresh scans when screen comes into focus (e.g., after delete)
  useFocusEffect(
    useCallback(() => {
      loadScans();
    }, [loadScans])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await loadScans();
    setRefreshing(false);
  };

  const filteredScans = scans.filter((scan) => {
    // Apply deer_sex filter
    if (filters.deer_sex && scan.deer_sex?.toLowerCase() !== filters.deer_sex.toLowerCase()) {
      return false;
    }
    
    // Apply recommendation filter
    if (filters.recommendation && scan.recommendation !== filters.recommendation) {
      return false;
    }
    
    // Apply search query filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase().trim();
      
      // Build a combined searchable string that matches UI display
      const searchableText = [
        scan.deer_type,
        scan.deer_sex,
        scan.notes,
        scan.body_condition,
        scan.recommendation,
        // Match display format: "Age: 4 yrs" or "4 yrs"
        scan.deer_age ? `${scan.deer_age} yrs` : null,
        scan.deer_age ? `age ${scan.deer_age}` : null,
        scan.deer_age ? `age: ${scan.deer_age}` : null,
        // Match display format: "8 points"
        scan.antler_points ? `${scan.antler_points} points` : null,
        scan.antler_points ? `${scan.antler_points} point` : null,
        scan.antler_points?.toString(),
        // Left/Right points
        scan.antler_points_left ? `${scan.antler_points_left}L` : null,
        scan.antler_points_right ? `${scan.antler_points_right}R` : null,
        // Confidence
        scan.confidence ? `${scan.confidence}%` : null,
        scan.confidence?.toString(),
        // Date formats
        scan.created_at ? format(new Date(scan.created_at), 'MMM d, yyyy') : null,
        scan.created_at ? format(new Date(scan.created_at), 'MMM d yyyy') : null,
        scan.created_at ? format(new Date(scan.created_at), 'MMMM') : null,
      ].filter(Boolean).join(' ').toLowerCase();
      
      return searchableText.includes(query);
    }
    
    return true;
  });

  const clearFilters = () => {
    setFilters({ deer_sex: '', recommendation: '' });
    setSearchQuery('');
  };

  const hasActiveFilters = filters.deer_sex || filters.recommendation || searchQuery;

  const renderScanCard = ({ item }: { item: Scan }) => {
    // Calculate calibrated confidence and check age uncertainty
    const ageIsUncertain = isAgeUncertain(item.deer_age);
    const displayConfidence = getCalibratedConfidence(item.confidence, item.deer_age);
    const ageDisplayText = getAgeDisplayText(item.deer_age);
    
    return (
      <TouchableOpacity
        activeOpacity={0.8}
        onPress={() => router.push(`/scan-result/${item.id}`)}
      >
        <View style={styles.scanCard}>
          <View style={styles.scanRow}>
            {/* Left side - Icon or Image */}
            <ScanImage localImageId={item.local_image_id} imageUrl={item.image_url} />
            
            {/* Middle - Info */}
            <View style={styles.scanInfo}>
              <View style={styles.statusBadge}>
                <Text style={[
                  styles.statusText,
                  item.recommendation === 'HARVEST' ? styles.harvestStatus : styles.passStatus
                ]}>
                  {item.recommendation || 'PASS'}
                </Text>
              </View>
              <View style={styles.ageRow}>
                <Text style={[styles.ageText, ageIsUncertain && styles.ageTextUncertain]}>
                  Age: {ageDisplayText}
                </Text>
                {ageIsUncertain && (
                  <AlertCircle size={12} color={colors.textMuted} style={styles.uncertainIcon} />
                )}
              </View>
              <Text style={styles.pointsText}>
                {item.antler_points || 0} points
                {(item.antler_points_left !== null || item.antler_points_right !== null) && 
                  ` (${item.antler_points_left || 0}L/${item.antler_points_right || 0}R)`}
              </Text>
              <Text style={styles.dateText}>
                {format(new Date(item.created_at), 'MMM d, yyyy')}
              </Text>
            </View>
            
            {/* Right side - Confidence */}
            <View style={[styles.confidenceContainer, ageIsUncertain && styles.confidenceContainerUncertain]}>
              <Text style={[styles.confidenceValue, ageIsUncertain && styles.confidenceValueUncertain]}>
                {displayConfidence}%
              </Text>
              <Text style={[styles.confidenceLabel, ageIsUncertain && styles.confidenceLabelUncertain]}>
                Model confidence
              </Text>
            </View>
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  // Empty State Component
  const EmptyState = () => (
    <View style={styles.emptyContainer}>
      {/* Camera Icon Circle */}
      <View style={styles.emptyIconCircle}>
        <Camera size={48} color={colors.textMuted} />
      </View>
      
      {/* Title & Description */}
      <Text style={styles.emptyTitle}>Build Your History</Text>
      <Text style={styles.emptyDescription}>
        Every scan you run will appear here with{'\n'}detailed analysis and recommendations
      </Text>
      
      {/* Example Card */}
      <View style={styles.exampleCard}>
        <View style={styles.exampleBadge}>
          <Text style={styles.exampleBadgeText}>EXAMPLE</Text>
        </View>
        
        <View style={styles.exampleContent}>
          {/* Left Icon */}
          <View style={styles.exampleIconBox}>
            <Target size={28} color={colors.textPrimary} />
          </View>
          
          {/* Middle Info */}
          <View style={styles.exampleInfo}>
            <View style={styles.exampleStatusBadge}>
              <Text style={styles.exampleStatusText}>PASS</Text>
            </View>
            <Text style={styles.exampleAgeText}>Age: 3.5 yrs</Text>
            <Text style={styles.examplePointsText}>8 points</Text>
            <Text style={styles.exampleSubText}>Your scans will show here</Text>
          </View>
          
          {/* Right Confidence */}
          <View style={styles.exampleConfidence}>
            <Text style={styles.exampleConfidenceValue}>87%</Text>
            <Text style={styles.exampleConfidenceLabel}>Model confidence</Text>
          </View>
        </View>
      </View>
      
      {/* CTA Button */}
      <TouchableOpacity 
        style={styles.scanButton}
        onPress={() => router.push('/(tabs)/scan')}
      >
        <Camera size={20} color={colors.background} />
        <Text style={styles.scanButtonText}>Scan Your First Deer</Text>
      </TouchableOpacity>
    </View>
  );

  if (!isAuthenticated) {
    // Redirect to login instead of showing auth required view
    router.replace('/(auth)/login');
    return null;
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerSpacer} />
        <Text style={styles.title}>History</Text>
        <TouchableOpacity style={styles.premiumBadge}>
          <Crown size={14} color={colors.primary} />
          <Text style={styles.premiumText}>Premium</Text>
        </TouchableOpacity>
      </View>

      {scans.length > 0 ? (
        <>
          {/* Search & Filters - Only show when there are scans */}
          <View style={styles.searchContainer}>
            <View style={styles.searchBar}>
              <Search size={20} color={colors.textMuted} />
              <TextInput
                style={styles.searchInput}
                placeholder="Search scans..."
                placeholderTextColor={colors.textMuted}
                value={searchQuery}
                onChangeText={setSearchQuery}
              />
              {searchQuery && (
                <TouchableOpacity onPress={() => setSearchQuery('')}>
                  <X size={18} color={colors.textMuted} />
                </TouchableOpacity>
              )}
            </View>
            <TouchableOpacity
              style={[styles.filterButton, hasActiveFilters && styles.filterButtonActive]}
              onPress={() => setShowFilters(!showFilters)}
            >
              <Filter size={20} color={hasActiveFilters ? colors.background : colors.textPrimary} />
            </TouchableOpacity>
          </View>

          {/* Filter Options */}
          {showFilters && (
            <View style={styles.filterOptions}>
              <View style={styles.filterRow}>
                <Text style={styles.filterLabel}>Sex:</Text>
                {['', 'Buck', 'Doe'].map((sex) => (
                  <TouchableOpacity
                    key={sex || 'all'}
                    style={[
                      styles.filterChip,
                      filters.deer_sex === sex && styles.filterChipActive,
                    ]}
                    onPress={() => setFilters({ ...filters, deer_sex: sex })}
                  >
                    <Text
                      style={[
                        styles.filterChipText,
                        filters.deer_sex === sex && styles.filterChipTextActive,
                      ]}
                    >
                      {sex || 'All'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              <View style={styles.filterRow}>
                <Text style={styles.filterLabel}>Rec:</Text>
                {['', 'HARVEST', 'PASS'].map((rec) => (
                  <TouchableOpacity
                    key={rec || 'all'}
                    style={[
                      styles.filterChip,
                      filters.recommendation === rec && styles.filterChipActive,
                    ]}
                    onPress={() => setFilters({ ...filters, recommendation: rec })}
                  >
                    <Text
                      style={[
                        styles.filterChipText,
                        filters.recommendation === rec && styles.filterChipTextActive,
                      ]}
                    >
                      {rec || 'All'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              {hasActiveFilters && (
                <TouchableOpacity style={styles.clearFilters} onPress={clearFilters}>
                  <Text style={styles.clearFiltersText}>Clear All Filters</Text>
                </TouchableOpacity>
              )}
            </View>
          )}

          {/* Scan List */}
          <FlatList
            data={filteredScans}
            keyExtractor={(item) => item.id}
            renderItem={renderScanCard}
            contentContainerStyle={[styles.listContent, { paddingBottom: insets.bottom + spacing.xl }]}
            showsVerticalScrollIndicator={false}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                tintColor={colors.primary}
              />
            }
            ListEmptyComponent={
              hasActiveFilters ? (
                <View style={styles.noResultsContainer}>
                  <Search size={48} color={colors.textMuted} />
                  <Text style={styles.noResultsTitle}>No Matching Scans</Text>
                  <Text style={styles.noResultsText}>
                    Try adjusting your filters or search query.
                  </Text>
                  <TouchableOpacity onPress={clearFilters}>
                    <Text style={styles.clearFiltersText}>Clear All Filters</Text>
                  </TouchableOpacity>
                </View>
              ) : null
            }
          />
        </>
      ) : (
        <ScrollView 
          contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.primary}
            />
          }
        >
          <EmptyState />
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  headerSpacer: {
    width: 40,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  headerRight: {
    width: 40,
  },
  premiumBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.backgroundCard,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    gap: spacing.xs,
  },
  premiumText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
  },
  searchContainer: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  searchBar: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  searchInput: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 16,
    paddingVertical: spacing.md,
  },
  filterButton: {
    width: 48,
    height: 48,
    borderRadius: borderRadius.md,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
  },
  filterButtonActive: {
    backgroundColor: colors.primary,
  },
  filterOptions: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    gap: spacing.sm,
  },
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  filterLabel: {
    color: colors.textSecondary,
    fontSize: 14,
    width: 40,
  },
  filterChip: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.full,
    backgroundColor: colors.backgroundCard,
  },
  filterChipActive: {
    backgroundColor: colors.primary,
  },
  filterChipText: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  filterChipTextActive: {
    color: colors.background,
    fontWeight: '600',
  },
  clearFilters: {
    alignSelf: 'flex-start',
    marginTop: spacing.xs,
  },
  clearFiltersText: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '500',
  },
  listContent: {
    padding: spacing.lg,
    paddingTop: 0,
    gap: spacing.md,
  },
  
  // Scan Card Styles
  scanCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  scanRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  scanIconBox: {
    width: 60,
    height: 60,
    borderRadius: borderRadius.md,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  thumbnail: {
    width: 60,
    height: 60,
    borderRadius: borderRadius.md,
    backgroundColor: colors.background,
  },
  scanInfo: {
    flex: 1,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
    marginBottom: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  harvestStatus: {
    color: colors.harvest,
  },
  passStatus: {
    color: colors.primary,
  },
  ageRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 2,
  },
  ageText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  ageTextUncertain: {
    color: colors.textMuted,
    fontStyle: 'italic',
  },
  uncertainIcon: {
    marginLeft: 4,
  },
  pointsText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  dateText: {
    fontSize: 12,
    color: colors.textMuted,
  },
  confidenceContainer: {
    alignItems: 'flex-end',
  },
  confidenceContainerUncertain: {
    opacity: 0.7,
  },
  confidenceValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  confidenceValueUncertain: {
    fontSize: 20,
    color: colors.textSecondary,
  },
  confidenceLabel: {
    fontSize: 11,
    color: colors.textMuted,
  },
  confidenceLabelUncertain: {
    fontSize: 10,
  },

  // Empty State Styles
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xxl,
  },
  emptyIconCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  emptyTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  emptyDescription: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.xl,
  },
  
  // Example Card Styles
  exampleCard: {
    width: '100%',
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.xl,
    position: 'relative',
  },
  exampleBadge: {
    position: 'absolute',
    top: spacing.sm,
    right: spacing.sm,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  exampleBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.background,
    letterSpacing: 0.5,
  },
  exampleContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  exampleIconBox: {
    width: 60,
    height: 60,
    borderRadius: borderRadius.md,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  exampleInfo: {
    flex: 1,
  },
  exampleStatusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
    backgroundColor: 'rgba(76, 175, 80, 0.2)',
    marginBottom: 4,
  },
  exampleStatusText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.harvest,
    letterSpacing: 0.5,
  },
  exampleAgeText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  examplePointsText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  exampleSubText: {
    fontSize: 12,
    color: colors.textMuted,
  },
  exampleConfidence: {
    alignItems: 'flex-end',
  },
  exampleConfidenceValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  exampleConfidenceLabel: {
    fontSize: 11,
    color: colors.textMuted,
  },

  // CTA Button
  scanButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.full,
    gap: spacing.sm,
    width: '100%',
  },
  scanButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },

  // No Results
  noResultsContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xxl,
  },
  noResultsTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  noResultsText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
});
