//package com.pipeline.config;
//
//import org.apache.kafka.clients.admin.NewTopic;
//import org.springframework.beans.factory.annotation.Value;
//import org.springframework.context.annotation.Bean;
//import org.springframework.context.annotation.Configuration;
//import org.springframework.kafka.config.TopicBuilder;
//
//@Configuration
//public class KafkaConfig {
//
//    @Value("${kafka.topics.logs}")
//    private String logsTopic;
//
//    @Value("${kafka.topics.events}")
//    private String eventsTopic;
//
//    @Value("${kafka.topics.alerts}")
//    private String alertsTopic;
//
//    @Bean
//    public NewTopic logsTopic() {
//        return TopicBuilder.name(logsTopic)
//                .partitions(3)
//                .replicas(1)
//                .build();
//    }
//
//    @Bean
//    public NewTopic eventsTopic() {
//        return TopicBuilder.name(eventsTopic)
//                .partitions(3)
//                .replicas(1)
//                .build();
//    }
//
//    @Bean
//    public NewTopic alertsTopic() {
//        return TopicBuilder.name(alertsTopic)
//                .partitions(1)
//                .replicas(2)
//                .build();
//    }
//}
