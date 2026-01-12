package com.pipeline.repository;

import com.pipeline.entity.LogEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface LogRepository extends JpaRepository<LogEntity, Long> {

    List<LogEntity> findByLevel(String level);

    List<LogEntity> findByService(String service);

    List<LogEntity> findByLevelAndService(String level, String service);

    @Query("SELECT l FROM LogEntity l WHERE l.timestamp BETWEEN :start AND :end")
    List<LogEntity> findByTimestampRange(@Param("start") Double start, @Param("end") Double end);

    @Query("SELECT l.level, COUNT(l) FROM LogEntity l GROUP BY l.level")
    List<Object[]> countByLevel();

    @Query("SELECT l.service, COUNT(l) FROM LogEntity l GROUP BY l.service")
    List<Object[]> countByService();

    long countByLevel(String level);
}
