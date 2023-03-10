# encoding:utf-8
import sys

sys.path.append("..")
import numpy as np
from mf import MF
from reader.trust import TrustGetter
from utility.matrix import SimMatrix
from utility.similarity import pearson_sp, cosine_sp, cos, adam_adar
from utility import util
import networkx as nx
from node2vec import Node2Vec as nv
import pandas as pd


class SocialReg(MF):
    """
    docstring for SocialReg

    Ma H, Zhou D, Liu C, et al. Recommender systems with social regularization[C]//Proceedings of the fourth ACM international conference on Web search and data mining. ACM, 2011: 287-296.
    """

    def __init__(self):
        super(SocialReg, self).__init__()
        # self.config.lambdaP = 0.001
        # self.config.lambdaQ = 0.001
        self.config.alpha = 0.1
        self.tg = TrustGetter()


        ###################################################################
        ######################### Partie modifiée #########################
        ###################################################################

        ### Initialisation du graphe Delicious et vectorisation avec Node2Vec 
        self.g_delicious = nx.read_edgelist("../data_delicious/user_contacts.dat", create_using=nx.Graph, nodetype=int, data=(("weight", int),("weight", int),("weight", int),("weight", int),("weight", int),("weight", int),))
        self.df_delicious = self.getNode2Vec(self.g_delicious)

        ### Initialisation du graphe Epinions et vectorisation avec Node2Vec 
        #self.g_epinions = nx.read_edgelist("../data_epinions/trust_data.txt", create_using=nx.DiGraph, nodetype=int, data=(("weight", int),))
        #self.df_epinions = self.getNode2Vec(self.g_epinions)
        
        # self.init_model()

    def getNode2Vec(self, g):
        ### Renvoie le dataframe du graphe g vectorisé avec Node2Vec
        WINDOW = 1
        MIN_COUNT = 1
        BATCH_WORDS = 4

        g_emb = nv(g, dimensions=16)

        md1 = g_emb.fit(
            vector_size = 16,
            window = WINDOW,
            min_count = MIN_COUNT,
            batch_words = BATCH_WORDS
        )

        emb_df = (
            pd.DataFrame(
                [md1.wv.get_vector(str(n)) for n in g.nodes()],
                index = g.nodes
            )
        )
        return emb_df

    def get_sim(self, u, k):
        ### Renvoie la similarité entre u et k
        
        #sim = (pearson_sp(self.rg.get_row(u), self.rg.get_row(k)) + 1.0) / 2.0  # fit the value into range [0.0,1.0]

        # Pour le calcul de la similarité Adamic-Adar pour le graphe Epinions
        #sim = adam_adar(u, k, self.g_epinions)

        # Pour le calcul de la similarité Adamic-Adar pour le graphe Delicious
        #sim = adam_adar(u, k, self.g_delicious)

        # Pour le calcul de la similarité Cosinus pour le graphe vectorisé avec Node2Vec de Epinions
        #sim = cos(u, k, self.df_epinions)

        # Pour le calcul de la similarité Cosinus pour le graphe vectorisé avec Node2Vec de Delicious
        sim = cos(u, k, self.df_delicious)
        return sim

    ###################################################################
    ###################################################################
    ###################################################################

    def init_model(self, k):
        super(SocialReg, self).init_model(k)
        from collections import defaultdict
        self.user_sim = SimMatrix()
        print('constructing user-user similarity matrix...')

        # self.user_sim = util.load_data('../data/sim/ft_cf_soreg08_cv1.pkl')

        for u in self.rg.user:
            for f in self.tg.get_followees(u):
                if self.user_sim.contains(u, f):
                    continue
                try:
                    sim = self.get_sim(u, f)
                except:
                    sim = 0
                self.user_sim.set(u, f, sim)

        # util.save_data(self.user_sim,'../data/sim/ft_cf_soreg08.pkl')


    def train_model(self, k):
        super(SocialReg, self).train_model(k)
        iteration = 0
        while iteration < self.config.maxIter:
            self.loss = 0
            for index, line in enumerate(self.rg.trainSet()):
                user, item, rating = line
                u = self.rg.user[user]
                i = self.rg.item[item]
                error = rating - self.predict(user, item)
                self.loss += 0.5 * error ** 2
                p, q = self.P[u], self.Q[i]

                social_term_p, social_term_loss = np.zeros((self.config.factor)), 0.0
                followees = self.tg.get_followees(user)
                for followee in followees:
                    if self.rg.containsUser(followee):
                        s = self.user_sim[user][followee]
                        uf = self.P[self.rg.user[followee]]
                        social_term_p += s * (p - uf)
                        social_term_loss += s * ((p - uf).dot(p - uf))

                social_term_m = np.zeros((self.config.factor))
                followers = self.tg.get_followers(user)
                for follower in followers:
                    if self.rg.containsUser(follower):
                        s = self.user_sim[user][follower]
                        ug = self.P[self.rg.user[follower]]
                        social_term_m += s * (p - ug)

                # update latent vectors
                self.P[u] += self.config.lr * (
                        error * q - self.config.alpha * (social_term_p + social_term_m) - self.config.lambdaP * p)
                self.Q[i] += self.config.lr * (error * p - self.config.lambdaQ * q)

                self.loss += 0.5 * self.config.alpha * social_term_loss

            self.loss += 0.5 * self.config.lambdaP * (self.P * self.P).sum() + 0.5 * self.config.lambdaQ * (
                    self.Q * self.Q).sum()

            iteration += 1
            if self.isConverged(iteration):
                break


if __name__ == '__main__':
    # srg = SocialReg()
    # srg.train_model(0)
    # coldrmse = srg.predict_model_cold_users()
    # print('cold start user rmse is :' + str(coldrmse))
    # srg.show_rmse()

    rmses = []
    maes = []
    tcsr = SocialReg()
    # print(bmf.rg.trainSet_u[1])
    for i in range(tcsr.config.k_fold_num):
        print('the %dth cross validation training' % i)
        tcsr.train_model(i)
        rmse, mae = tcsr.predict_model()
        rmses.append(rmse)
        maes.append(mae)
    rmse_avg = sum(rmses) / 5
    mae_avg = sum(maes) / 5
    print("the rmses are %s" % rmses)
    print("the maes are %s" % maes)
    print("the average of rmses is %s " % rmse_avg)
    print("the average of maes is %s " % mae_avg)
